"""bot 内置监控面板（core.web_panel）：真实 HTTP 起服（ephemeral 端口）全链路测试。

运行: python -m pytest test/test_web_panel.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import core.context as ctx
from core import config
from core.auth import make_login_key
from core.web_panel import make_server


class _FakePlugin:
    description = "测试插件描述"


def _register_fakes():
    class FakeDice(_FakePlugin):
        __module__ = "plugins.fake_dice"

    class FakeMenu(_FakePlugin):
        __module__ = "plugins.menu"  # 借用真实系统插件 key 验证 SYSTEM 判定

    ctx.plugin_registry.extend([FakeDice, FakeMenu])
    return [FakeDice, FakeMenu]


def _req(url, method="GET", key=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    if data:
        r.add_header("Content-Type", "application/json")
    if key:
        r.add_header("Authorization", "Bearer " + key)
    try:
        with urllib.request.urlopen(r, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


class WebPanelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fakes = _register_fakes()
        cls.server = make_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        for f in cls.fakes:
            ctx.plugin_registry.remove(f)

    def setUp(self):
        self.super_key = make_login_key(str(config.SUPER_USER[0]))
        self.normal_key = make_login_key("999")
        conn = sqlite3.connect(str(config.DB_PATH))
        conn.execute("DELETE FROM group_plugin_config WHERE group_id = 555")
        conn.commit()
        conn.close()

    def test_page_served(self):
        with urllib.request.urlopen(self.base + "/", timeout=5) as resp:
            html = resp.read().decode()
        self.assertEqual(resp.status, 200)
        self.assertIn("监控面板", html)

    def test_auth_matrix(self):
        s, _ = _req(self.base + "/api/scopes")
        self.assertEqual(s, 401)
        s, _ = _req(self.base + "/api/scopes", key=self.normal_key)
        self.assertEqual(s, 403)
        s, body = _req(self.base + "/api/scopes", key=self.super_key)
        self.assertEqual(s, 200)
        gids = [x["group_id"] for x in body["scopes"]]
        self.assertIn(0, gids)
        self.assertIn(config.DEFAULT_GROUP_ID, gids)

    def test_plugin_list_from_registry(self):
        s, body = _req(self.base + f"/api/plugins?group_id=555", key=self.super_key)
        self.assertEqual(s, 200)
        by_key = {p["key"]: p for p in body["plugins"]}
        self.assertIn("fake_dice", by_key)
        self.assertFalse(by_key["fake_dice"]["system"])
        self.assertEqual(by_key["fake_dice"]["description"], "测试插件描述")
        self.assertTrue(by_key["menu"]["system"], "menu 应按 SYSTEM_PLUGINS 判定")

    def test_toggle_roundtrip(self):
        s, _ = _req(self.base + "/api/plugins", method="PUT", key=self.super_key,
                   body={"group_id": 555, "plugin_key": "fake_dice", "enabled": True})
        self.assertEqual(s, 200)
        conn = sqlite3.connect(str(config.DB_PATH))
        hit = conn.execute(
            "SELECT 1 FROM group_plugin_config WHERE group_id=555 AND plugin_name='fake_dice'"
        ).fetchone()
        conn.close()
        self.assertIsNotNone(hit)
        s, _ = _req(self.base + "/api/plugins", method="PUT", key=self.super_key,
                    body={"group_id": 555, "plugin_key": "fake_dice", "enabled": False})
        conn = sqlite3.connect(str(config.DB_PATH))
        hit = conn.execute(
            "SELECT 1 FROM group_plugin_config WHERE group_id=555 AND plugin_name='fake_dice'"
        ).fetchone()
        conn.close()
        self.assertIsNone(hit)
        s, body = _req(self.base + "/api/plugins", method="PUT", key=self.super_key,
                       body={"group_id": 555, "plugin_key": "menu", "enabled": False})
        self.assertEqual(s, 400)

    def test_config_roundtrip(self):
        s, body = _req(self.base + "/api/config", key=self.super_key)
        self.assertEqual(s, 200)
        orig = Path(config.CONFIG_PATH).read_text(encoding="utf-8")
        self.assertEqual(body["yaml"], orig)
        s, body = _req(self.base + "/api/config", method="PUT", key=self.super_key,
                       body={"yaml": "bot: [broken"})
        self.assertEqual(s, 400)
        self.assertEqual(Path(config.CONFIG_PATH).read_text(encoding="utf-8"), orig, "非法不得落盘")
        s, _ = _req(self.base + "/api/config", method="PUT", key=self.super_key,
                    body={"yaml": orig + "\n# panel edit test\n"})
        self.assertEqual(s, 200)
        self.assertTrue((Path(str(config.CONFIG_PATH) + ".bak")).is_file())
        s, body = _req(self.base + "/api/config", key=self.super_key)
        self.assertIn("# panel edit test", body["yaml"])


if __name__ == "__main__":
    unittest.main()
