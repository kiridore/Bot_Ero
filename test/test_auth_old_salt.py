"""多盐轮换：换盐后旧密钥仍可验证（无感迁移）。"""
import sys
import unittest
from unittest.mock import patch


class TestOldSalt(unittest.TestCase):
    def test_old_salt_key_still_verifies(self):
        from core import auth
        with patch("core.auth.AUTH_SALT", "new-salt"), \
             patch("core.auth.AUTH_SALT_OLD", ["old-salt"]):
            old_key = auth.make_login_key(123456)
            self.assertEqual(auth.verify_login_key(old_key), "123456")

    def test_new_salt_key_verifies(self):
        from core import auth
        with patch("core.auth.AUTH_SALT", "new-salt"), \
             patch("core.auth.AUTH_SALT_OLD", ["old-salt"]):
            new_key = auth.make_login_key(123456)
            self.assertEqual(auth.verify_login_key(new_key), "123456")

    def test_wrong_key_rejected(self):
        from core import auth
        with patch("core.auth.AUTH_SALT", "new-salt"), \
             patch("core.auth.AUTH_SALT_OLD", ["old-salt"]):
            self.assertIsNone(auth.verify_login_key("fake:key"))

    def test_salt_old_config_parsing(self):
        import importlib
        import os
        import tempfile
        from pathlib import Path
        from core import config
        # 完整必填配置（缺任一必填节会在 reload 时 SystemExit），auth 带 old_salts 列表
        cfg_text = (
            "bot:\n"
            "  qq: \"123456\"\n"
            "  nickname: 测试bot\n"
            "  super_users: [1, 2]\n"
            "  default_group: 42\n"
            "  ws_url: ws://127.0.0.1:3001\n"
            "  ws_token: \"123456\"\n"
            "  llonebot_data_path: /tmp/onebot_data\n"
            "  python_data_path: ./server_data\n"
            "onebot:\n"
            "  http_url: http://127.0.0.1:3000\n"
            "  token: \"123456\"\n"
            "auth:\n"
            "  salt: new-salt\n"
            "  old_salts: ['a', ' b', 'c']\n"
            "timeline:\n"
            "  url: http://127.0.0.1:8765\n"
            "  token: test-timeline-token\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            cfg_file = Path(tmp) / "config.yaml"
            cfg_file.write_text(cfg_text, encoding="utf-8")
            old = os.environ.get("BOTERO_CONFIG")
            os.environ["BOTERO_CONFIG"] = str(cfg_file)
            try:
                importlib.reload(config)
                self.assertEqual(config.AUTH_SALT_OLD, ["a", " b", "c"])
            finally:
                if old is None:
                    os.environ.pop("BOTERO_CONFIG", None)
                else:
                    os.environ["BOTERO_CONFIG"] = old
                importlib.reload(config)


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=2))
