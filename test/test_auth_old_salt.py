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
        from core import config
        with patch.dict("os.environ", {"BOTERO_AUTH_SALT_OLD": "a, b, ,c"}):
            import importlib
            importlib.reload(config)
            self.assertEqual(config.AUTH_SALT_OLD, ["a", " b", "c"])
        importlib.reload(config)


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=2))
