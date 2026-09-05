# cloud-mail 发信客户端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `core/mail_client.py` 调用自建 cloud-mail（Skymail）API 发邮件，配置走统一 `config.yaml`，供后续插件/webapp 功能复用。

**Architecture:** 单模块 best-effort 客户端（照 `core/onebot_client.py` 先例）：登录换 token（模块级缓存、失效重登一次）、发件 accountId 经 `GET /api/account/list` 自动发现并 `lru_cache`、唯一入口 `send_email()` 返回 `(bool, str)` 绝不抛出。配置为 `config.yaml` 可选 `mail:` 节，留空即功能关闭。

**Tech Stack:** requests（已有依赖）+ unittest.mock（进程内测试，不真发信）。

**Spec:** 无独立 spec 文件（bounded 路径，设计经用户两轮确认——初始版 + 统一配置合并后修订版）。决策要点随计划携带如下：

- 鉴权走官方 `POST /api/login`（email+password → token，`Authorization` 头**不加 Bearer 前缀**）；弃用的 `public/genToken` 不用
- 发信 `POST /api/email/send`：`accountId` + `receiveEmail[]` + `subject` + `content`(HTML) + 可选 `text/name/attachments[]`（Base64，≤10）
- 配置：`mail.url/email/password/sender_name` 全可选，不进 `_REQUIRED`
- `config.X` 属性访问（禁止导入期绑定，遵守 specs/conventions.md §测试隔离与文案同步）

## Global Constraints

- bot 进程禁 async/await（本模块纯同步）
- 配置读取一律模块属性访问（`config.CLOUDMAIL_URL`），禁止 `from core.config import` 单名导入
- 新增 `mail:` 节为可选节：未配置时模块返回 `(False, "邮箱服务未配置")`，不报错不抛出
- Commit 中文 + Conventional Commits；本任务为内部新模块（无用户可见变化）：CHANGELOG 记 `[未发布]` 节、**不 bump** `BOTERO_VERSION`
- 测试 mock `requests.request`，不真实联网；全量 `pytest` 全绿（当前基线 317 passed）
- API 权威文档：https://doc.skymail.ink/api/api-doc.html（已读，本计划代码即按其契约）

---

### Task 1: 配置节 + mail_client 模块 + 测试 + 文档（单任务单 commit）

**Files:**
- Modify: `core/config.py`（`_mail` 节 + 4 常量，放「直播 / 工具箱」段之后）
- Modify: `config.example.yaml`（文件末尾追加 mail 节模板）
- Create: `core/mail_client.py`
- Create: `test/test_mail_client.py`
- Modify: `kb/OPERATIONS.md`（外部 API 清单表 +1 行）
- Modify: `CHANGELOG.md`（`[未发布]` 节 +1 条）

**Interfaces:**
- Consumes: `config.CLOUDMAIL_URL/EMAIL/PASSWORD/SENDER_NAME`（本任务新增）；`requests.request`
- Produces: `send_email(to: list[str], subject: str, html: str, text: str | None = None, sender_name: str | None = None, attachments: list[tuple[str, bytes, str | None]] | None = None) -> tuple[bool, str]`（后续插件/webapp 复用的唯一入口）

- [ ] **Step 1: 写失败测试**

创建 `test/test_mail_client.py`：

```python
"""cloud-mail 发信客户端（core.mail_client）测试：mock requests，不真实联网。

运行: python -m pytest test/test_mail_client.py
"""

from __future__ import annotations

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


def _login_ok():
    return _resp({"code": 200, "message": "success", "data": {"token": "TOK1"}})


def _acct_ok():
    return _resp({"code": 200, "message": "success", "data": [{"accountId": 7, "email": "bot@x.com"}]})


def _send_ok():
    return _resp({"code": 200, "message": "success", "data": [{"emailId": 999}]})


class _Recorder:
    """按 URL 路径分派假响应并记录调用。"""

    def __init__(self, routes: dict[str, dict], seq: list[dict] | None = None):
        self.routes = routes          # path 后缀 → 响应 dict（每次调用取用）
        self.seq = seq or []          # 同 path 需要序列响应时用 (path, resp) 列表
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
        rec = _Recorder({"/api/login": _login_ok().__dict__, "/api/account/list?size=1": _acct_ok().__dict__,
                         "/api/email/send": _send_ok().__dict__})
        # _Recorder 返回 _resp 包装，直接给 dict 不行——改为传已构造响应：
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
        self.assertEqual(kw["headers"]["Authorization"], "TOK1")  # 不带 Bearer
        import base64
        self.assertEqual(kw["json"]["attachments"][0]["content"], base64.b64encode(b"data").decode())

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

        def boom(*a, **k):
            raise _rq.ConnectionError("refused")

        with patch("core.mail_client.requests.request", side_effect=boom):
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


if __name__ == "__main__":
    unittest.main()
```

注意：`test_send_ok_payload_and_headers` 里第一个 `rec =` 赋值是草稿残留，**实现时删除第一行 `rec = _Recorder({..._login_ok().__dict()...})` 只保留第二个构造**（传入 dict 的版本）。`_login_ok/_acct_ok/_send_ok` 三个 helper 若最终未被引用则一并删除。

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest test/test_mail_client.py -v`
Expected: FAIL/ERROR — `core.mail_client` 不存在（ModuleNotFoundError）

- [ ] **Step 3: 实现**

`core/config.py`「直播 / 工具箱」段之后追加：

```python
# —— cloud-mail 邮件（可选；url/email/password 留空 = 功能关闭）——
_mail = _sec("mail")
CLOUDMAIL_URL = str(_mail.get("url") or "")
CLOUDMAIL_EMAIL = str(_mail.get("email") or "")
CLOUDMAIL_PASSWORD = str(_mail.get("password") or "")
CLOUDMAIL_SENDER_NAME = str(_mail.get("sender_name") or "")
```

`config.example.yaml` 末尾追加：

```yaml
mail:
  url: ""            # cloud-mail（Skymail）站点基地址；留空 = 邮件功能关闭
  email: ""          # 发件账号（管理员邮箱，登录换 token 用）
  password: ""
  sender_name: ""    # 发件人显示名（可选，空则自动截取邮箱前缀）
```

创建 `core/mail_client.py`：

```python
"""cloud-mail（Skymail）发信客户端：登录换 token、发件账号自动发现、best-effort 发邮件。

API 文档：https://doc.skymail.ink/api/api-doc.html
配置：config.yaml mail 节（可选；url/email/password 任一为空 = 功能关闭）。
属性访问 config.*（不用导入期绑定，遵守 specs/conventions.md §测试隔离与文案同步）。
"""

import base64
from functools import lru_cache

import requests

from core import config

_TIMEOUT = 15
_MAX_ATTACHMENTS = 10  # 服务端上限

# ponytail: token 进程内缓存；服务端换密钥需重启进程才重登，可接受
_token: str | None = None


def _configured() -> bool:
    return bool(config.CLOUDMAIL_URL and config.CLOUDMAIL_EMAIL and config.CLOUDMAIL_PASSWORD)


def _call(method: str, path: str, *, token: str | None = None, json_body: dict | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token  # 文档要求：不加 Bearer 前缀
    try:
        resp = requests.request(
            method, f"{config.CLOUDMAIL_URL.rstrip('/')}{path}",
            headers=headers, json=json_body, timeout=_TIMEOUT)
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return int(data.get("code") or 0), data


def _login(force: bool = False) -> str | None:
    global _token
    if _token and not force:
        return _token
    result = _call("POST", "/api/login", json_body={
        "email": config.CLOUDMAIL_EMAIL, "password": config.CLOUDMAIL_PASSWORD})
    if not result or result[0] != 200:
        return None
    token = (result[1].get("data") or {}).get("token")
    if not token:
        return None
    _token = str(token)
    return _token


@lru_cache(maxsize=1)
def _account_id() -> int | None:
    token = _login()
    if not token:
        return None
    result = _call("GET", "/api/account/list?size=1", token=token)
    if not result or result[0] != 200:
        return None
    items = result[1].get("data") or []
    if not items:
        return None
    return int(items[0]["accountId"])


def send_email(
    to: list[str],
    subject: str,
    html: str,
    text: str | None = None,
    sender_name: str | None = None,
    attachments: list[tuple[str, bytes, str | None]] | None = None,
) -> tuple[bool, str]:
    """发邮件（best-effort，绝不抛出）。attachments: [(文件名, 内容, MIME|None)]。

    返回 (成功?, 说明)。未配置时返回 (False, "邮箱服务未配置")，功能可安全闲置。
    """
    if not _configured():
        return False, "邮箱服务未配置"
    if not subject or not html:
        return False, "主题与正文不能为空"
    to = [str(x).strip() for x in (to or []) if str(x).strip()]
    if not to:
        return False, "收件人不能为空"
    if attachments and len(attachments) > _MAX_ATTACHMENTS:
        return False, f"附件最多 {_MAX_ATTACHMENTS} 个"

    global _token
    account_id = _account_id()
    if account_id is None:
        # accountId/token 可能过期：清缓存强制重登重试一次
        _token = None
        _account_id.cache_clear()
        account_id = _account_id()
    if account_id is None:
        return False, "无法获取发件账号（登录失败或无邮箱账号）"
    token = _login()
    if not token:
        return False, "登录失败"

    payload: dict = {
        "accountId": account_id,
        "receiveEmail": to,
        "subject": subject,
        "content": html,
    }
    if text:
        payload["text"] = text
    name = sender_name or config.CLOUDMAIL_SENDER_NAME
    if name:
        payload["name"] = name
    if attachments:
        payload["attachments"] = [
            {
                "filename": fname,
                "content": base64.b64encode(data).decode("ascii"),
                **({"contentType": mime} if mime else {}),
            }
            for fname, data, mime in attachments
        ]

    result = _call("POST", "/api/email/send", token=token, json_body=payload)
    if result is None:
        return False, "网络错误或超时"
    code, body = result
    if code == 200:
        return True, "ok"
    # token 失效：强制重登再试一次（非 token 类失败重试无害，仍失败即返回服务端消息）
    fresh = _login(force=True)
    if fresh:
        result = _call("POST", "/api/email/send", token=fresh, json_body=payload)
        if result and result[0] == 200:
            return True, "ok"
    return False, str(body.get("message") or f"发送失败（code={code}）")
```

- [ ] **Step 4: 运行测试通过**

Run: `python -m pytest test/test_mail_client.py -v`
Expected: 8 passed

- [ ] **Step 5: 文档**

`kb/OPERATIONS.md`「外部 API 清单」表追加一行：

```markdown
| cloud-mail | `<mail.url 配置>` | 自建邮箱系统发信（`core/mail_client.py`） |
```

`CHANGELOG.md` `[未发布]` 节追加（不 bump 版本——内部模块，无用户可见变化）：

```markdown
- **邮件客户端**：新增 `core/mail_client.py`（cloud-mail/Skymail API：登录 token 缓存、发件账号自动发现、best-effort 发信含附件）；`config.yaml` 新增可选 `mail` 节启用，留空即关闭。暂无调用方，为后续邮件通知功能铺底
```

- [ ] **Step 6: 全量回归 + 提交**

Run: `python -m pytest`
Expected: 325 passed（317 基线 + 8 新增），0 failed

```bash
git add core/config.py config.example.yaml core/mail_client.py test/test_mail_client.py kb/OPERATIONS.md CHANGELOG.md
git commit -m "feat(邮件): cloud-mail 发信客户端模块"
```

---

## 自审记录

- **设计覆盖**：登录鉴权/无 Bearer ✓、accountId 自动发现 + lru_cache ✓、失效重登一次（含 accountId 失效双通道）✓、附件 Base64 ≤10 ✓、未配置短路 ✓、属性访问配置 ✓、超时不抛出 ✓。
- **占位符扫描**：Step 1 测试代码中标注了一处需删除的草稿残留行（`_login_ok().__dict__` 版本），已显式指明删除动作——除此之外无 TBD/TODO。
- **类型一致性**：`send_email` 签名在测试（8 用例）与实现一致；`config.CLOUDMAIL_*` 四常量命名与 `patch.multiple` 的键一致；`_Recorder` 同时支持路由表与序列响应两种分派（覆盖 token 失效重试时序）。
- **测试隔离**：全 mock requests，无网络/DB/文件路径依赖，conftest 无需为 mail 节做任何 override。
