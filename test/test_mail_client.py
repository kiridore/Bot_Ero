"""cloud-mail 发信客户端（core.mail_client）测试：mock requests，不真实联网。

运行: python -m pytest test/test_mail_client.py
"""

from __future__ import annotations

import base64
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import core.mail_client as mail_client
from core import config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _resp(payload: dict):
    class _R:
        def json(self_inner):
            return payload

    return _R()


class _Recorder:
    """按 URL 路径分派假响应并记录调用；seq 提供同路径的时序响应。"""

    def __init__(self, routes: dict[str, dict], seq: list[tuple[str, dict]] | None = None):
        self.routes = routes
        self.seq = seq or []
        self.calls = []

    def __call__(self, method, url, **kw):
        path = url.replace("https://mail.example.com", "")
        if self.seq:
            for i, (p, resp) in enumerate(self.seq):
                if p == path:
                    self.seq.pop(i)
                    self.calls.append((method, path, kw))
                    return _resp(resp)
        self.calls.append((method, path, kw))
        return _resp(self.routes[path])


CFG = dict(CLOUDMAIL_URL="https://mail.example.com", CLOUDMAIL_EMAIL="bot@x.com",
           CLOUDMAIL_PASSWORD="pw", CLOUDMAIL_SENDER_NAME="小埃")


class MailClientTest(unittest.TestCase):
    def setUp(self):
        mail_client._token = None
        mail_client._account_id.cache_clear()
        self._cfg = patch.multiple(config, **CFG)
        self._cfg.start()
        self.addCleanup(self._cfg.stop)

    def test_unconfigured_short_circuit(self):
        with patch.multiple(config, CLOUDMAIL_URL="", CLOUDMAIL_EMAIL="", CLOUDMAIL_PASSWORD=""):
            with patch("core.mail_client.requests.request") as req:
                ok, msg = mail_client.send_email(["a@x.com"], "s", "<p>h</p>")
        self.assertFalse(ok)
        self.assertIn("未配置", msg)
        req.assert_not_called()

    def test_send_ok_payload_and_headers(self):
        rec = _Recorder({
            "/api/login": {"code": 200, "data": {"token": "TOK1"}},
            "/api/account/list?size=1": {"code": 200, "data": [{"accountId": 7}]},
            "/api/email/send": {"code": 200, "data": [{"emailId": 999}]},
        })
        with patch("core.mail_client.requests.request", side_effect=rec):
            ok, msg = mail_client.send_email(
                ["a@x.com", " b@x.com "], "标题", "<p>正文</p>", text="正文",
                attachments=[("f.txt", b"data", "text/plain")])
        self.assertTrue(ok)
        send = next(c for c in rec.calls if c[1] == "/api/email/send")
        kw = send[2]
        self.assertEqual(kw["json"]["accountId"], 7)
        self.assertEqual(kw["json"]["receiveEmail"], ["a@x.com", "b@x.com"])
        self.assertEqual(kw["json"]["subject"], "标题")
        self.assertEqual(kw["json"]["name"], "小埃")
        self.assertEqual(kw["json"]["attachments"][0]["filename"], "f.txt")
        self.assertEqual(kw["json"]["attachments"][0]["contentType"], "text/plain")
        self.assertEqual(kw["json"]["attachments"][0]["content"], base64.b64encode(b"data").decode())
        self.assertEqual(kw["headers"]["Authorization"], "TOK1")  # 不带 Bearer

    def test_token_cached_across_sends(self):
        rec = _Recorder({
            "/api/login": {"code": 200, "data": {"token": "TOK1"}},
            "/api/account/list?size=1": {"code": 200, "data": [{"accountId": 7}]},
            "/api/email/send": {"code": 200, "data": []},
        })
        with patch("core.mail_client.requests.request", side_effect=rec):
            mail_client.send_email(["a@x.com"], "s", "<p>h</p>")
            mail_client.send_email(["a@x.com"], "s2", "<p>h</p>")
        logins = [c for c in rec.calls if c[1] == "/api/login"]
        self.assertEqual(len(logins), 1, "token 应缓存，仅登录一次")

    def test_expired_token_relogin_once(self):
        rec = _Recorder({}, seq=[
            ("/api/login", {"code": 200, "data": {"token": "OLD"}}),
            ("/api/account/list?size=1", {"code": 200, "data": [{"accountId": 7}]}),
            ("/api/email/send", {"code": 401, "message": "token失效"}),
            ("/api/login", {"code": 200, "data": {"token": "NEW"}}),
            ("/api/email/send", {"code": 200, "data": []}),
        ])
        with patch("core.mail_client.requests.request", side_effect=rec):
            ok, msg = mail_client.send_email(["a@x.com"], "s", "<p>h</p>")
        self.assertTrue(ok)
        logins = [c for c in rec.calls if c[1] == "/api/login"]
        self.assertEqual(len(logins), 2, "失效后强制重登恰好一次")

    def test_send_rejected_by_server(self):
        rec = _Recorder({}, seq=[
            ("/api/login", {"code": 200, "data": {"token": "TOK1"}}),
            ("/api/account/list?size=1", {"code": 200, "data": [{"accountId": 7}]}),
            ("/api/email/send", {"code": 400, "message": "参数错误"}),
            ("/api/login", {"code": 200, "data": {"token": "TOK1"}}),
            ("/api/email/send", {"code": 400, "message": "参数错误"}),
        ])
        with patch("core.mail_client.requests.request", side_effect=rec):
            ok, msg = mail_client.send_email(["a@x.com"], "s", "<p>h</p>")
        self.assertFalse(ok)
        self.assertIn("参数错误", msg)

    def test_no_account_available(self):
        rec = _Recorder({
            "/api/login": {"code": 200, "data": {"token": "TOK1"}},
            "/api/account/list?size=1": {"code": 200, "data": []},
        })
        with patch("core.mail_client.requests.request", side_effect=rec):
            ok, msg = mail_client.send_email(["a@x.com"], "s", "<p>h</p>")
        self.assertFalse(ok)
        self.assertIn("发件账号", msg)

    def test_network_error(self):
        import requests as _rq

        # 登录/账号发现成功，发送阶段断网 → 网络错误文案
        def dispatch(method, url, **kw):
            path = url.replace("https://mail.example.com", "")
            if path == "/api/login":
                return _resp({"code": 200, "data": {"token": "TOK1"}})
            if path == "/api/account/list?size=1":
                return _resp({"code": 200, "data": [{"accountId": 7}]})
            raise _rq.ConnectionError("refused")

        with patch("core.mail_client.requests.request", side_effect=dispatch):
            ok, msg = mail_client.send_email(["a@x.com"], "s", "<p>h</p>")
        self.assertFalse(ok)
        self.assertIn("网络", msg)

    def test_bad_inputs(self):
        with patch("core.mail_client.requests.request") as req:
            self.assertIn("不能为空", mail_client.send_email([], "s", "<p>h</p>")[1])
            self.assertIn("不能为空", mail_client.send_email(["a@x.com"], "", "<p>h</p>")[1])
        atts = [(f"f{i}.txt", b"x", None) for i in range(11)]
        self.assertIn("附件最多", mail_client.send_email(["a@x.com"], "s", "<p>h</p>", attachments=atts)[1])
        req.assert_not_called()


    def test_proxy_scoped_to_cloud_mail_only(self):
        """mail.proxy 仅注入本客户端请求：配置时全部请求带 proxies，未配置时 None。"""
        routes = {
            "/api/login": {"code": 200, "data": {"token": "t0"}},
            "/api/account/list?size=1": {"code": 200, "data": [{"accountId": 7}]},
            "/api/email/send": {"code": 200, "data": {"id": 1}},
        }
        rec = _Recorder(routes)
        with patch("core.mail_client.requests.request", side_effect=rec):
            self.assertTrue(mail_client.send_email(["a@x.com"], "s", "<p>h</p>")[0])
        self.assertTrue(rec.calls)
        self.assertTrue(all(kw.get("proxies") is None for _, _, kw in rec.calls))

        rec2 = _Recorder(routes)
        with patch.multiple(config, CLOUDMAIL_PROXY="http://127.0.0.1:7890"):
            with patch("core.mail_client.requests.request", side_effect=rec2):
                self.assertTrue(mail_client.send_email(["a@x.com"], "s", "<p>h</p>")[0])
        expected = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
        self.assertTrue(rec2.calls)
        self.assertTrue(all(kw.get("proxies") == expected for _, _, kw in rec2.calls))


if __name__ == "__main__":
    unittest.main()
