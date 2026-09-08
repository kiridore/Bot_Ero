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

# 社区形态最小配置：无 default_group / onebot / timeline 节
COMMUNITY_MINIMAL = """
bot:
  edition: community
  qq: "123456"
  nickname: 测试bot
  super_users: [1, 2]
  ws_url: ws://127.0.0.1:3001
  ws_token: "123456"
  llonebot_data_path: /tmp/onebot_data
  python_data_path: ./server_data
auth:
  salt: test-salt
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

    def test_community_minimal_loads_without_web_side_keys(self):
        """社区形态：缺 default_group / onebot / timeline 不退出。"""
        from core.config import _load
        with tempfile.TemporaryDirectory() as tmp:
            data = _load(Path(_write(tmp, COMMUNITY_MINIMAL)))
            self.assertEqual(data["bot"]["edition"], "community")

    def test_private_missing_default_group_exits(self):
        """私有形态（缺省 edition）：default_group 仍必填。"""
        from core.config import _load
        with tempfile.TemporaryDirectory() as tmp:
            bad = yaml.safe_load(REQUIRED_MINIMAL)
            del bad["bot"]["default_group"]
            p = Path(tmp) / "config.yaml"
            p.write_text(yaml.safe_dump(bad), encoding="utf-8")
            with self.assertRaises(SystemExit) as ctx:
                _load(p)
            self.assertIn("bot.default_group", str(ctx.exception))

    def test_invalid_edition_exits(self):
        """非法 edition 值启动即退出并提示可选值。"""
        from core.config import _load
        with tempfile.TemporaryDirectory() as tmp:
            bad = yaml.safe_load(REQUIRED_MINIMAL)
            bad["bot"]["edition"] = "saas"
            p = Path(tmp) / "config.yaml"
            p.write_text(yaml.safe_dump(bad), encoding="utf-8")
            with self.assertRaises(SystemExit) as ctx:
                _load(p)
            self.assertIn("bot.edition", str(ctx.exception))


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
                self.assertEqual(cfg.EDITION, "private")
                self.assertEqual(cfg.COMMUNITY_CMD_COOLDOWN_SECONDS, 0)  # private 缺省 0=频控关闭（T1.5 契约）
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

    def test_community_constants(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._reload_with(_write(tmp, COMMUNITY_MINIMAL))
            try:
                self.assertEqual(cfg.EDITION, "community")
                self.assertIsNone(cfg.DEFAULT_GROUP_ID)      # 社区形态无默认群
                self.assertIsNone(cfg.GROUP_ID)              # 旧名别名跟随
                self.assertEqual(cfg.TIMELINE_URL, "")       # 空 = 上报关闭（T0.3 消费）
                self.assertEqual(cfg.TIMELINE_TOKEN, "")
                self.assertEqual(cfg.ONEBOT_HTTP_URL, "")
                self.assertEqual(cfg.SYSTEM_PLUGINS_CONF, [])
                self.assertEqual(cfg.COMMUNITY_MAX_GROUPS, 50)
                self.assertEqual(cfg.COMMUNITY_CMD_COOLDOWN_SECONDS, 3)
            finally:
                import core.config as cfg2
                importlib.reload(cfg2)

    def test_edition_default_private_and_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = yaml.safe_load(REQUIRED_MINIMAL)
            raw["bot"]["system_plugins"] = ["menu", "register"]
            raw["community"] = {"max_groups": 5, "cmd_cooldown_seconds": 10}
            cfg = self._reload_with(_write(tmp, yaml.safe_dump(raw, allow_unicode=True)))
            try:
                self.assertEqual(cfg.EDITION, "private")     # 无 edition 键 → 缺省 private
                self.assertEqual(cfg.DEFAULT_GROUP_ID, 42)
                self.assertEqual(cfg.SYSTEM_PLUGINS_CONF, ["menu", "register"])
                self.assertEqual(cfg.COMMUNITY_MAX_GROUPS, 5)
                self.assertEqual(cfg.COMMUNITY_CMD_COOLDOWN_SECONDS, 10)  # 显式覆盖不分形态
            finally:
                import core.config as cfg2
                importlib.reload(cfg2)


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=2))
