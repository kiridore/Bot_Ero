"""新设置键默认值与读写回归。运行: pytest test/test_user_settings_privacy.py"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import user_settings as us


class TestPrivacyKeys(unittest.TestCase):
    def setUp(self):
        us.SETTINGS_ROOT = Path("/tmp/test_settings_keys")
        import shutil
        shutil.rmtree(us.SETTINGS_ROOT, ignore_errors=True)

    def test_defaults_true(self):
        self.assertTrue(us.private_checkin_public("333"))
        self.assertTrue(us.checkin_image_public("333"))

    def test_toggle_roundtrip(self):
        us.update_settings("333", {"privacy": {"private_checkin_public": False}})
        self.assertFalse(us.private_checkin_public("333"))
        self.assertTrue(us.checkin_image_public("333"))


if __name__ == "__main__":
    unittest.main()
