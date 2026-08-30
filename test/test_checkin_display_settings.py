"""打卡显示状态四态设置与旧键一次性迁移回归。运行: pytest test/test_checkin_display_settings.py"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import user_settings as us


class TestCheckinDisplay(unittest.TestCase):
    def setUp(self):
        import shutil
        us.SETTINGS_ROOT = Path("/tmp/test_checkin_display")
        shutil.rmtree(us.SETTINGS_ROOT, ignore_errors=True)

    def _write(self, uid, privacy):
        us.update_settings(uid, {"privacy": privacy})

    def test_default_show(self):
        self.assertEqual(us.checkin_display("1"), {"private": "show", "group": "show"})

    def test_roundtrip_all_states(self):
        for state in us.CHECKIN_DISPLAY_STATES:
            self._write("2", {"checkin_display_private": state, "checkin_display_group": state})
            self.assertEqual(us.checkin_display("2"), {"private": state, "group": state})

    def test_migration_old_private_false(self):
        self._write("3", {"private_checkin_public": False})
        d = us.checkin_display("3")
        self.assertEqual(d, {"private": "hidden", "group": "show"})
        raw = us.get_settings("3").get("privacy", {})  # 迁移已回写，旧键删除
        self.assertNotIn("private_checkin_public", raw)
        self.assertNotIn("checkin_image_public", raw)

    def test_migration_old_image_false(self):
        self._write("4", {"checkin_image_public": False})
        self.assertEqual(us.checkin_display("4"), {"private": "blur", "group": "blur"})

    def test_migration_both_old_keys_hidden_wins_for_private(self):
        self._write("5", {"private_checkin_public": False, "checkin_image_public": False})
        self.assertEqual(us.checkin_display("5"), {"private": "hidden", "group": "blur"})

    def test_migration_ignored_when_new_keys_exist(self):
        self._write("6", {"checkin_display_private": "text", "private_checkin_public": False})
        self.assertEqual(us.checkin_display("6"), {"private": "text", "group": "show"})

    def test_invalid_value_falls_back_show(self):
        self._write("7", {"checkin_display_private": "爆炸"})
        self.assertEqual(us.checkin_display("7")["private"], "show")


if __name__ == "__main__":
    unittest.main()
