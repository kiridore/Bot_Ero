"""DND 5E 建卡校验：属性生成方式、购点预算、技能与豁免数量、HP 计算。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.trpg import character as dnd


def _card(**over):
    base = {
        "rules": "dnd5e",
        "race": "人类",
        "class_name": "战士",
        "attributes_mode": "point_buy",
        "str_score": 15, "dex_score": 14, "con_score": 14,
        "int_score": 10, "wis_score": 10, "cha_score": 8,
        "proficient_skills": ["运动", "威吓"],
        "saving_profs": ["力量", "体质"],
        "level": 1,
    }
    base.update(over)
    return base


class TestPointBuy(unittest.TestCase):
    def test_valid_card(self):
        self.assertEqual(dnd.validate(_card()), [])

    def test_spent_points(self):
        # 15=9, 14=7, 14=7, 10=2, 10=2, 8=0 → 27
        self.assertEqual(dnd.point_buy_spent(_card()), 27)

    def test_over_budget(self):
        card = _card(str_score=15, dex_score=15, con_score=15, int_score=15, wis_score=15, cha_score=15)
        problems = dnd.validate(card)
        self.assertTrue(any("购点超出预算" in p for p in problems), problems)

    def test_out_of_range_in_point_buy(self):
        problems = dnd.validate(_card(str_score=18))
        self.assertTrue(any("购点值需在 8-15" in p for p in problems), problems)


class TestOtherModes(unittest.TestCase):
    def test_rolled_range(self):
        problems = dnd.validate(_card(attributes_mode="rolled", str_score=19))
        self.assertTrue(any("掷骰结果应在 3-18" in p for p in problems), problems)

    def test_array_values(self):
        problems = dnd.validate(_card(attributes_mode="array", str_score=9))
        self.assertTrue(any("标准数组" in p for p in problems), problems)

    def test_manual_range(self):
        problems = dnd.validate(_card(attributes_mode="manual", str_score=0))
        self.assertTrue(any("应在 1-30" in p for p in problems), problems)

    def test_unknown_mode(self):
        problems = dnd.validate(_card(attributes_mode="gacha"))
        self.assertTrue(any("未知的属性生成方式" in p for p in problems), problems)


class TestSkillAndSaveLimits(unittest.TestCase):
    def test_too_many_skills(self):
        problems = dnd.validate(_card(proficient_skills=["运动", "威吓", "察觉"]))
        self.assertTrue(any("最多选 2 项" in p for p in problems), problems)

    def test_skill_outside_class_list(self):
        problems = dnd.validate(_card(proficient_skills=["奥术"]))
        self.assertTrue(any("不可选技能" in p for p in problems), problems)

    def test_bard_any_skill(self):
        card = _card(class_name="吟游诗人", proficient_skills=["奥术", "历史", "表演"],
                     attributes_mode="manual", saving_profs=["敏捷", "魅力"])
        self.assertEqual(dnd.validate(card), [])

    def test_unknown_skill(self):
        problems = dnd.validate(_card(proficient_skills=["飞天"]))
        self.assertTrue(any("未知技能" in p for p in problems), problems)

    def test_too_many_saves(self):
        problems = dnd.validate(_card(saving_profs=["力量", "体质", "敏捷"]))
        self.assertTrue(any("豁免熟练最多 2 项" in p for p in problems), problems)

    def test_unknown_race_and_class(self):
        problems = dnd.validate(_card(race="喵人", class_name="召唤师"))
        self.assertTrue(any("未知种族" in p for p in problems), problems)
        self.assertTrue(any("未知职业" in p for p in problems), problems)


class TestSuggestedHp(unittest.TestCase):
    def test_level_one_takes_full_die(self):
        self.assertEqual(dnd.suggest_hp({"class_name": "战士", "con_score": 14, "level": 1}), 12)

    def test_multi_level_uses_average(self):
        # 1 级 10+2，之后每级 6+2
        self.assertEqual(dnd.suggest_hp({"class_name": "战士", "con_score": 14, "level": 5}), 44)

    def test_low_con_never_below_one(self):
        self.assertGreaterEqual(dnd.suggest_hp({"class_name": "法师", "con_score": 1, "level": 1}), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
