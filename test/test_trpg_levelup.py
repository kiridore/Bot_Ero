"""DND 5E 升级：等级判定、HP 增长、属性提升与历史记录。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.trpg import levelup


def _card(**over):
    card = {
        "rules": "dnd5e", "char_name": "艾伦", "race": "人类", "class_name": "战士",
        "level": 1, "xp": 300,
        "str_score": 15, "dex_score": 14, "con_score": 14,
        "int_score": 10, "wis_score": 10, "cha_score": 8,
        "hp": 12, "current_hp": 12,
        "proficient_skills": ["运动", "威吓"],
    }
    card.update(over)
    return card


class TestStatus(unittest.TestCase):
    def test_not_enough_xp(self):
        state = levelup.status(_card(xp=299))
        self.assertFalse(state["can_level_up"])
        self.assertEqual(state["xp_to_next"], 1)

    def test_enough_xp(self):
        state = levelup.status(_card(xp=300))
        self.assertTrue(state["can_level_up"])
        self.assertEqual(state["next_threshold"], 300)

    def test_max_level(self):
        state = levelup.status(_card(level=20, xp=999999))
        self.assertFalse(state["can_level_up"])
        self.assertIsNone(state["next_threshold"])

    def test_level_clamped(self):
        self.assertEqual(levelup.current_level(_card(level=99)), 20)
        self.assertEqual(levelup.current_level(_card(level=0)), 1)

    def test_asi_required_levels(self):
        for level in (3, 7, 11, 15, 18):
            self.assertTrue(levelup.asi_required(level), level)
        for level in (1, 2, 4, 5, 19):
            self.assertFalse(levelup.asi_required(level), level)


class TestHpGain(unittest.TestCase):
    def test_average_plus_con(self):
        self.assertEqual(levelup.hp_gain(_card(), "average"), 8)

    def test_roll_plus_con(self):
        self.assertEqual(levelup.hp_gain(_card(), "roll", roll=7), 9)

    def test_roll_out_of_range(self):
        with self.assertRaises(ValueError):
            levelup.hp_gain(_card(), "roll", roll=11)

    def test_low_con_never_below_one(self):
        card = _card(con_score=1, race="精灵")
        self.assertGreaterEqual(levelup.hp_gain(card, "average"), 1)

    def test_unknown_mode(self):
        with self.assertRaises(ValueError):
            levelup.hp_gain(_card(), "gacha")


class TestAsi(unittest.TestCase):
    def test_single_plus_two(self):
        self.assertEqual(levelup.validate_asi(_card(), {"str": 2}), {"str": 2})

    def test_two_plus_one(self):
        self.assertEqual(levelup.validate_asi(_card(), {"str": 1, "dex": 1}), {"str": 1, "dex": 1})

    def test_chinese_names_accepted(self):
        self.assertEqual(levelup.validate_asi(_card(), {"力量": 2}), {"str": 2})

    def test_wrong_total(self):
        with self.assertRaises(ValueError):
            levelup.validate_asi(_card(), {"str": 3})
        with self.assertRaises(ValueError):
            levelup.validate_asi(_card(), {"str": 1})

    def test_three_attributes_rejected(self):
        with self.assertRaises(ValueError):
            levelup.validate_asi(_card(), {"str": 1, "dex": 1, "con": 1})

    def test_cap_20_with_race_bonus(self):
        # 人类 +1：基础 19 + 种族 1 = 20，再加 1 超限
        with self.assertRaises(ValueError):
            levelup.validate_asi(_card(str_score=19), {"str": 1, "dex": 1})
        self.assertEqual(levelup.validate_asi(_card(str_score=18), {"str": 1, "dex": 1}),
                         {"str": 1, "dex": 1})

    def test_unknown_attribute(self):
        with self.assertRaises(ValueError):
            levelup.validate_asi(_card(), {"luck": 2})


class TestApply(unittest.TestCase):
    def test_level_and_hp(self):
        card = _card()
        result = levelup.apply_level_up(card, "average")
        self.assertEqual(result["level"], 2)
        self.assertEqual(result["hp_gain"], 8)
        self.assertEqual(card["level"], 2)
        self.assertEqual(card["hp"], 20)
        self.assertEqual(card["current_hp"], 20)
        self.assertEqual(len(card["level_history"]), 1)

    def test_history_appends(self):
        card = _card()
        levelup.apply_level_up(card, "average")
        card["xp"] = 900
        levelup.apply_level_up(card, "roll", roll=10)
        self.assertEqual([h["level"] for h in card["level_history"]], [2, 3])
        self.assertEqual(card["level_history"][1]["hp_gain"], 12)

    def test_asi_applied_on_fourth(self):
        card = _card(level=3, xp=2700)
        result = levelup.apply_level_up(card, "average", {"str": 1, "dex": 1})
        self.assertEqual(result["asi"], {"str": 1, "dex": 1})
        self.assertEqual(card["str_score"], 16)
        self.assertEqual(card["dex_score"], 15)
        self.assertEqual(card["level_history"][0]["asi"], {"str": 1, "dex": 1})

    def test_asi_required_at_fourth(self):
        card = _card(level=3, xp=2700)
        with self.assertRaises(ValueError):
            levelup.apply_level_up(card, "average")
        self.assertEqual(card["level"], 3)

    def test_no_asi_on_plain_level(self):
        card = _card()
        result = levelup.apply_level_up(card, "average", {"str": 2})
        self.assertEqual(result["asi"], {})
        self.assertEqual(card["str_score"], 15)

    def test_features_appended(self):
        card = _card(features="战斗风格")
        levelup.apply_level_up(card, "average", features_text="动作如潮")
        self.assertEqual(card["features"], "战斗风格\n动作如潮")

    def test_not_enough_xp(self):
        with self.assertRaises(ValueError):
            levelup.apply_level_up(_card(xp=299), "average")

    def test_max_level_refused(self):
        with self.assertRaises(ValueError):
            levelup.apply_level_up(_card(level=20, xp=999999), "average")


if __name__ == "__main__":
    unittest.main(verbosity=2)
