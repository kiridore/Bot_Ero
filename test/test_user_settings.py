"""测试 core.user_settings 通用个人设置模块。

运行: pytest test/test_user_settings.py
"""

from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import user_settings as us


class UserSettingsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = patch.object(us, "SETTINGS_ROOT", Path(self._tmp.name))
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def test_default_empty(self):
        self.assertEqual(us.get_settings("123"), {})

    def test_default_privacy_public(self):
        self.assertTrue(us.privacy_public("123"))

    def test_update_and_get(self):
        us.update_settings("123", {"privacy": {"char_public": False}})
        self.assertEqual(us.get_settings("123"), {"privacy": {"char_public": False}})
        self.assertFalse(us.privacy_public("123"))

    def test_deep_merge_keeps_other_keys(self):
        us.update_settings("123", {"privacy": {"char_public": False}})
        us.update_settings("123", {"other_feature": {"flag": True}})
        settings = us.get_settings("123")
        self.assertEqual(settings["privacy"], {"char_public": False})
        self.assertEqual(settings["other_feature"], {"flag": True})

    def test_update_overwrites_scalar(self):
        us.update_settings("123", {"privacy": {"char_public": True}})
        us.update_settings("123", {"privacy": {"char_public": False}})
        self.assertFalse(us.privacy_public("123"))

    def test_isolated_between_users(self):
        us.update_settings("123", {"privacy": {"char_public": False}})
        self.assertTrue(us.privacy_public("456"))

    def test_new_preferences_default_without_writing(self):
        self.assertTrue(us.identity_public(123))
        self.assertTrue(us.show_others_checkin(123))
        self.assertTrue(us.watermark_enabled(123))
        self.assertEqual(list(Path(self._tmp.name).iterdir()), [])

    def test_new_preferences_persist_and_merge_without_extension(self):
        for group, key in (("privacy", "identity_public"),
                           ("timeline", "show_others_checkin"), ("watermark", "enabled")):
            us.update_settings(123, {group: {key: False}})
        self.assertFalse(us.identity_public(123))
        self.assertFalse(us.show_others_checkin(123))
        self.assertFalse(us.watermark_enabled(123))
        self.assertTrue((Path(self._tmp.name) / "123").is_file())
        self.assertFalse((Path(self._tmp.name) / "123.json").exists())
        self.assertTrue(us.identity_public(456))
        us.update_settings(123, {"privacy": {"identity_public": True}})
        self.assertTrue(us.identity_public(123))
        self.assertFalse(us.watermark_enabled(123))

    def test_new_preferences_reject_non_booleans(self):
        for group, key in (("privacy", "identity_public"),
                           ("timeline", "show_others_checkin"), ("watermark", "enabled")):
            for value in ("false", "true", 0, 1, None, [], {}):
                with self.subTest(group=group, value=value), self.assertRaises(ValueError):
                    us.update_settings(123, {group: {key: value}})
        self.assertEqual(us.get_settings(123), {})

    def test_anonymous_name_normalizes_qq(self):
        expected = hashlib.md5(b"123").hexdigest()[:8]
        for uid in (123, "123", " 00123 "):
            self.assertEqual(us.anonymous_name(uid), expected)
        for invalid in (None, True, "abc", "../123", "１２３", 1.5):
            with self.subTest(uid=invalid), self.assertRaises(ValueError):
                us.anonymous_name(invalid)

    def test_display_identity_owner_public_and_hidden(self):
        original = ("真实昵称", "https://example.test/avatar.png")
        self.assertEqual(us.display_identity(123, 456, *original), original)
        us.update_settings(123, {"privacy": {"identity_public": False}})
        self.assertEqual(us.display_identity("00123", 123, *original), original)
        expected = (us.anonymous_name(123), "/identicon/123.png")
        self.assertEqual(us.display_identity(123, "456", *original), expected)
        self.assertEqual(us.display_identity(123, None, *original), expected)
        self.assertEqual(us.display_identity(123, 123, "真实昵称", None), ("真实昵称", None))
        self.assertEqual(us.get_settings(123), {"privacy": {"identity_public": False}})

    def test_rejects_bad_user_id(self):
        with self.assertRaises(ValueError):
            us.update_settings("../evil", {"a": 1})


if __name__ == "__main__":
    unittest.main(verbosity=2)
