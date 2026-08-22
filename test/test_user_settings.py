"""测试 core.user_settings 通用个人设置模块。

运行: pytest test/test_user_settings.py
"""

from __future__ import annotations

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

    def test_rejects_bad_user_id(self):
        with self.assertRaises(ValueError):
            us.update_settings("../evil", {"a": 1})


if __name__ == "__main__":
    unittest.main(verbosity=2)
