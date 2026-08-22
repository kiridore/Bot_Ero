"""测试 core.character_store 角色 JSON 存储层。

运行: pytest test/test_character_store.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import character_store as store


def _base_data() -> dict:
    return {
        "char_name": "艾伦", "race": "精灵", "class_name": "法师",
        "level": 1, "background": "", "str_score": 8, "dex_score": 14,
        "con_score": 12, "int_score": 15, "wis_score": 13, "cha_score": 10,
        "proficient_skills": ["奥术"], "hp": 0, "ac": 0, "notes": "",
    }


class CharacterStoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = patch.object(store, "CHARS_ROOT", Path(self._tmp.name))
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def test_create_and_get(self):
        cid = store.create_char("123", _base_data())
        got = store.get_char("123", cid)
        self.assertEqual(got["char_name"], "艾伦")
        self.assertEqual(got["id"], cid)
        self.assertIsNone(store.get_char("456", cid))  # 跨用户不可见

    def test_create_first_auto_current(self):
        cid = store.create_char("123", _base_data())
        self.assertEqual(store.get_current("123")["id"], cid)

    def test_list_order_and_set_current(self):
        c1 = store.create_char("123", _base_data())
        c2 = store.create_char("123", _base_data())
        ids = [c["id"] for c in store.list_chars("123")]
        self.assertEqual(ids, [c1, c2])
        store.set_current("123", c1)
        self.assertEqual(store.get_current("123")["id"], c1)

    def test_delete_current_switches_to_next(self):
        c1 = store.create_char("123", _base_data())
        c2 = store.create_char("123", _base_data())
        store.delete_char("123", c1)
        self.assertEqual(store.get_current("123")["id"], c2)
        store.delete_char("123", c2)
        self.assertIsNone(store.get_current("123"))
        self.assertEqual(store.list_chars("123"), [])

    def test_update_replaces_data(self):
        cid = store.create_char("123", _base_data())
        data = _base_data()
        data["char_name"] = "改名"
        store.update_char("123", cid, data)
        self.assertEqual(store.get_char("123", cid)["char_name"], "改名")

    def test_rejects_bad_ids(self):
        with self.assertRaises(ValueError):
            store.create_char("abc", _base_data())
        with self.assertRaises(ValueError):
            store.create_char("1.5", _base_data())
        cid = store.create_char("123", _base_data())
        with self.assertRaises(ValueError):
            store.update_char("123", f"{cid}x", _base_data())
        with self.assertRaises(ValueError):
            store.set_current("123", "999")  # 不存在的角色

    def test_meta_order_after_delete(self):
        c1 = store.create_char("123", _base_data())
        c2 = store.create_char("123", _base_data())
        store.delete_char("123", c1)
        meta = json.loads((store.CHARS_ROOT / "123" / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["order"], [c2])
        self.assertEqual(meta["current_id"], c2)

    def test_atomic_write_leaves_no_tmp(self):
        cid = store.create_char("123", _base_data())
        leftovers = list((store.CHARS_ROOT / "123").glob("*.tmp"))
        self.assertEqual(leftovers, [])

    def test_update_missing_char_raises(self):
        with self.assertRaises(ValueError):
            store.update_char("123", "999", _base_data())

    def test_create_after_meta_loss_does_not_overwrite(self):
        c1 = store.create_char("123", _base_data())
        (store.CHARS_ROOT / "123" / "meta.json").unlink()
        c2 = store.create_char("123", _base_data())
        self.assertNotEqual(c2, c1)
        self.assertIsNotNone(store.get_char("123", c1))
        self.assertIsNotNone(store.get_char("123", c2))


if __name__ == "__main__":
    unittest.main(verbosity=2)
