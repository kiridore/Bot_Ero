"""测试 core.trpg.character.finalize 的 5E 派生计算扩展。

运行: python3 test/test_trpg_finalize.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.trpg.character import finalize


def _base(**kw) -> dict:
    data = {
        "char_name": "艾伦", "race": "人类", "class_name": "法师", "level": 1,
        "str_score": 15, "dex_score": 14, "con_score": 13,
        "int_score": 12, "wis_score": 10, "cha_score": 8,
        "proficient_skills": [], "hp": 0, "ac": 0,
    }
    data.update(kw)
    return data


class TestProficiencyBonus(unittest.TestCase):
    def test_level1_is_2(self):
        self.assertEqual(finalize(_base(level=1))["prof_bonus"], 2)

    def test_level5_is_3(self):
        self.assertEqual(finalize(_base(level=5))["prof_bonus"], 3)

    def test_level9_is_4(self):
        self.assertEqual(finalize(_base(level=9))["prof_bonus"], 4)

    def test_level17_is_6(self):
        self.assertEqual(finalize(_base(level=17))["prof_bonus"], 6)


class TestSavingThrows(unittest.TestCase):
    # 人类 +1 全属性；str 15+1=16 → 加值 +3；dex 14+1=15 → +2
    def test_no_prof_is_ability_mod(self):
        data = finalize(_base())
        self.assertEqual(data["save_mods"]["力量"], 3)
        self.assertEqual(data["save_mods"]["敏捷"], 2)

    def test_prof_adds_proficiency(self):
        data = finalize(_base(saving_profs=["力量"]))
        self.assertEqual(data["save_mods"]["力量"], 3 + 2)
        self.assertEqual(data["save_mods"]["敏捷"], 2)

    def test_missing_saving_profs_defaults_empty(self):
        data = finalize(_base())
        self.assertEqual(data["save_mods"]["魅力"], -1)


class TestDerived(unittest.TestCase):
    def test_passive_perception(self):
        data = finalize(_base(wis_score=14))  # 人类 +1 → 15 → +2
        self.assertEqual(data["passive_perception"], 12)

    def test_passive_perception_with_proficiency(self):
        data = finalize(_base(wis_score=14, proficient_skills=["察觉"]))
        self.assertEqual(data["passive_perception"], 14)

    def test_initiative_is_dex_mod(self):
        data = finalize(_base())
        self.assertEqual(data["initiative"], 2)

    def test_hit_dice_uses_class_die(self):
        data = finalize(_base(class_name="法师"))  # d6
        self.assertEqual(data["hit_dice"], "1d6")
        data = finalize(_base(class_name="野蛮人", level=3))  # d12
        self.assertEqual(data["hit_dice"], "3d12")

    def test_old_data_without_new_keys(self):
        data = finalize(_base())
        for key in ("prof_bonus", "save_mods", "passive_perception", "initiative", "hit_dice"):
            self.assertIn(key, data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
