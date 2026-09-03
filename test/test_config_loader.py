"""config.yaml 加载器：必填校验、缺文件提示、默认值与类型转换。"""
import importlib
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REQUIRED_MINIMAL = """
bot:
  qq: "123456"
  nickname: 测试bot
  super_users: [1, 2]
  default_group: 42
  ws_url: ws://127.0.0.1:3001
  ws_token: "123456"
  llonebot_data_path: /tmp/onebot_data
  python_data_path: ./server_data
onebot:
  http_url: http://127.0.0.1:3000
  token: "123456"
auth:
  salt: test-salt
timeline:
  url: http://127.0.0.1:8765
  token: test-timeline-token
"""


def _write(tmp: str, content: str) -> str:
    p = Path(tmp) / "config.yaml"
    p.write_text(content, encoding="utf-8")
    return str(p)


class TestLoad(unittest.TestCase):
    def test_missing_file_exits_with_hint(self):
        from core.config import _load
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as ctx:
                _load(Path(tmp) / "none.yaml")
            self.assertIn("config.example.yaml", str(ctx.exception))

    def test_missing_required_key_exits(self):
        from core.config import _load
        with tempfile.TemporaryDirectory() as tmp:
            # 缺 bot.qq
            bad = yaml.safe_load(REQUIRED_MINIMAL)
            del bad["bot"]["qq"]
            p = Path(tmp) / "config.yaml"
            p.write_text(yaml.safe_dump(bad), encoding="utf-8")
            with self.assertRaises(SystemExit) as ctx:
                _load(p)
            self.assertIn("bot.qq", str(ctx.exception))

    def test_empty_required_value_exits(self):
        from core.config import _load
        with tempfile.TemporaryDirectory() as tmp:
            bad = yaml.safe_load(REQUIRED_MINIMAL)
            bad["auth"]["salt"] = ""
            p = Path(tmp) / "config.yaml"
            p.write_text(yaml.safe_dump(bad), encoding="utf-8")
            with self.assertRaises(SystemExit):
                _load(p)


class TestConstants(unittest.TestCase):
    """模块级常量：reload 后类型与默认值正确，退出时恢复 conftest 配置。"""

    def _reload_with(self, cfg_path: str):
        import os
        old = os.environ.get("BOTERO_CONFIG")
        os.environ["BOTERO_CONFIG"] = cfg_path
        import core.config as cfg
        try:
            importlib.reload(cfg)
            return cfg
        finally:
            if old is None:
                os.environ.pop("BOTERO_CONFIG", None)
            else:
                os.environ["BOTERO_CONFIG"] = old

    def test_types_and_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._reload_with(_write(tmp, REQUIRED_MINIMAL))
            try:
                self.assertEqual(cfg.BOT_QQ, "123456")          # str，非 int
                self.assertIsInstance(cfg.BOT_QQ, str)
                self.assertEqual(cfg.SUPER_USER, [1, 2])
                self.assertEqual(cfg.DEFAULT_GROUP_ID, 42)
                self.assertEqual(cfg.GROUP_ID, 42)              # 两旧名合并为一键
                self.assertEqual(cfg.WS_TOKEN, "123456")
                self.assertEqual(cfg.DOWNLOAD_PROXY, "")        # 可选默认无代理
                self.assertIsNone(cfg.ICON_PROXY)
                self.assertTrue(cfg.WEEKLY_NOTIFY_ENABLED)
                self.assertEqual(cfg.DB_PATH, cfg.PROJECT_ROOT / "data.db")
                self.assertEqual(
                    cfg.MESSAGE_LOG_DB_PATH, cfg.PROJECT_ROOT / "server_data" / "message_log.db"
                )
                self.assertEqual(cfg.CHECKIN_MAX_BYTES, 10 * 1024 * 1024)
                self.assertEqual(cfg.AUTH_SALT_OLD, [])
            finally:
                import core.config as cfg2
                importlib.reload(cfg2)  # 恢复 conftest 临时配置

    def test_auth_old_salts_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = yaml.safe_load(REQUIRED_MINIMAL)
            raw["auth"]["old_salts"] = ["a", " b", "c"]  # YAML 原样保留空格
            cfg = self._reload_with(_write(tmp, yaml.safe_dump(raw, allow_unicode=True)))
            try:
                self.assertEqual(cfg.AUTH_SALT_OLD, ["a", " b", "c"])
            finally:
                import core.config as cfg2
                importlib.reload(cfg2)


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=2))
