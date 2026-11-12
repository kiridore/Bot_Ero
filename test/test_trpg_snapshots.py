"""跑团记录里的角色卡快照：字段压缩、开录与结束两份。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.trpg import snapshots


def _dnd_card(**over):
    card = {
        "rules": "dnd5e", "char_name": "艾伦", "race": "人类", "class_name": "战士",
        "level": 3, "xp": 2700,
        "str_score": 15, "dex_score": 14, "con_score": 14,
        "int_score": 10, "wis_score": 10, "cha_score": 8,
        "hp": 30, "current_hp": 22,
        "proficient_skills": ["运动", "威吓"], "saving_profs": ["力量", "体质"],
    }
    card.update(over)
    return card


def _coc_card(**over):
    card = {
        "rules": "coc7th", "char_name": "田宫真莉", "occupation": "药剂师", "age": 28,
        "str_score": 60, "con_score": 55, "siz_score": 45, "dex_score": 55,
        "app_score": 60, "int_score": 85, "pow_score": 65, "edu_score": 45,
        "current_hp": 8, "current_san": 40, "current_mp": 13,
        "skills": {"侦察": {"base": 25, "occupation": 20}},
    }
    card.update(over)
    return card


class TestSheetSnapshot(unittest.TestCase):
    def test_dnd_snapshot(self):
        snap = snapshots.sheet_snapshot(_dnd_card())
        self.assertEqual(snap["rules"], "dnd5e")
        self.assertEqual(snap["level"], 3)
        self.assertEqual(snap["hp"], 30)
        self.assertEqual(snap["current_hp"], 22)
        self.assertEqual(snap["prof_bonus"], 2)
        self.assertIn("运动", snap["proficient_skills"])

    def test_coc_snapshot_keeps_totals(self):
        snap = snapshots.sheet_snapshot(_coc_card())
        self.assertEqual(snap["rules"], "coc7th")
        self.assertEqual(snap["current_san"], 40)
        self.assertEqual(snap["san"], 65)
        self.assertEqual(snap["skills"]["侦察"], 45)

    def test_snapshot_skips_bulky_text(self):
        snap = snapshots.sheet_snapshot(_dnd_card(notes="x" * 5000, equipment=["剑", "盾"]))
        self.assertNotIn("notes", snap)
        self.assertNotIn("equipment", snap)


class TestAttachEndSnapshots(unittest.TestCase):
    def _meta(self):
        return {"participants": [
            {"user_id": "111", "char_id": 3, "char_name": "旧名", "role": "dm"},
            {"user_id": "222", "char_name": "无卡"},
        ]}

    def test_attaches_sheet_end(self):
        meta = self._meta()
        cards = {("111", 3): _coc_card()}
        with patch("core.trpg.snapshots.store.get_char",
                   side_effect=lambda uid, cid: cards.get((uid, cid))):
            snapshots.attach_end_snapshots(meta)
        first = meta["participants"][0]
        self.assertEqual(first["sheet_end"]["current_san"], 40)
        self.assertEqual(first["char_name"], "田宫真莉")
        self.assertNotIn("sheet_end", meta["participants"][1])

    def test_deleted_card_skipped(self):
        meta = self._meta()
        with patch("core.trpg.snapshots.store.get_char", return_value=None):
            snapshots.attach_end_snapshots(meta)
        self.assertNotIn("sheet_end", meta["participants"][0])
        self.assertEqual(meta["participants"][0]["char_name"], "旧名")

    def test_missing_char_id_skipped(self):
        meta = {"participants": [{"user_id": "222", "char_name": "无卡"}]}
        with patch("core.trpg.snapshots.store.get_char") as getter:
            snapshots.attach_end_snapshots(meta)
        getter.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
