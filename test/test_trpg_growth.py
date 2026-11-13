"""COC 幕间成长：成长标记、成长检定、90%+ 理智奖励，以及大失败口径。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.trpg import coc, growth
from core.trpg.vitals import clamp


def _coc_card(**over):
    card = {
        "rules": "coc7th", "char_name": "田宫真莉", "occupation": "药剂师",
        "str_score": 60, "con_score": 55, "siz_score": 45, "dex_score": 55,
        "app_score": 60, "int_score": 85, "pow_score": 65, "edu_score": 45,
        "current_hp": 10, "current_san": 65,
        "skills": {
            "侦察": {"base": 25, "growth": 0, "occupation": 0, "interest": 0},
            "图书馆": {"base": 20, "growth": 0, "occupation": 0, "interest": 0},
        },
    }
    card.update(over)
    return card


class TestGradeRules(unittest.TestCase):
    """5.5：≥50 只有 100 大失败；<50 是 96-100；01 大成功。"""

    def _grade(self, value, roll):
        from plugins.trpg_dice.rolls import coc_check
        with patch("plugins.trpg_dice.rolls.random.randint", return_value=roll):
            return coc_check(value)[1]

    def test_critical_success(self):
        self.assertEqual(self._grade(60, 1), "大成功")

    def test_high_skill_only_fumbles_on_100(self):
        self.assertEqual(self._grade(60, 96), "失败")
        self.assertEqual(self._grade(60, 99), "失败")
        self.assertEqual(self._grade(60, 100), "大失败")

    def test_low_skill_fumbles_on_96_to_100(self):
        self.assertEqual(self._grade(40, 95), "失败")
        self.assertEqual(self._grade(40, 96), "大失败")
        self.assertEqual(self._grade(40, 100), "大失败")

    def test_skill_over_100_is_allowed(self):
        self.assertEqual(self._grade(120, 99), "常规成功")
        self.assertEqual(self._grade(120, 100), "大失败")


class TestImproves(unittest.TestCase):
    def test_greater_than_skill(self):
        self.assertTrue(growth.improves(30, 25))

    def test_equal_does_not_improve(self):
        self.assertFalse(growth.improves(25, 25))

    def test_above_95_always_improves(self):
        self.assertTrue(growth.improves(96, 90))
        self.assertTrue(growth.improves(100, 99))

    def test_95_against_high_skill_does_not(self):
        self.assertFalse(growth.improves(95, 95))


class TestMark(unittest.TestCase):
    def test_mark_known_skill(self):
        card = _coc_card()
        self.assertTrue(growth.mark(card, "侦察"))
        self.assertEqual(growth.checked_skills(card), ["侦察"])

    def test_alias_marks_canonical_skill(self):
        card = _coc_card(skills={"侦察": {"base": 25, "growth": 0}})
        self.assertTrue(growth.mark(card, "侦查"))
        self.assertEqual(growth.checked_skills(card), ["侦察"])

    def test_unknown_skill_not_marked(self):
        card = _coc_card()
        self.assertFalse(growth.mark(card, "御剑术"))
        self.assertEqual(growth.checked_skills(card), [])


class TestSettle(unittest.TestCase):
    def _settle(self, card, rolls):
        with patch("core.trpg.growth.random.randint", side_effect=rolls):
            return growth.settle(card)

    def test_improves_and_clears_marks(self):
        card = _coc_card()
        growth.mark(card, "侦察")
        # 检定骰 90（>25）→ 增长骰 4
        details, san = self._settle(card, [90, 4])
        self.assertEqual(details, [("侦察", 25, 90, 4, 29)])
        self.assertEqual(card["skills"]["侦察"]["growth"], 4)
        self.assertFalse(card["skills"]["侦察"]["check"])

    def test_no_gain_when_roll_below_value(self):
        card = _coc_card()
        growth.mark(card, "侦察")
        details, _ = self._settle(card, [10])
        self.assertEqual(details, [("侦察", 25, 10, 0, 25)])
        self.assertEqual(card["skills"]["侦察"]["growth"], 0)

    def test_growth_can_exceed_100(self):
        card = _coc_card(skills={"侦察": {"base": 25, "growth": 90}})
        growth.mark(card, "侦察")
        details, _ = self._settle(card, [99, 10, 3, 4])
        self.assertEqual(details[0][4], 125)
        self.assertEqual(coc.skill_value(card, "侦察"), 125)

    def test_unmarked_skills_untouched(self):
        card = _coc_card()
        details, _ = self._settle(card, [])
        self.assertEqual(details, [])

    def test_san_reward_once_for_any_ninety_skill(self):
        card = _coc_card(skills={"侦察": {"base": 25, "growth": 90}, "图书馆": {"base": 95}})
        growth.mark(card, "侦察")
        details, san = self._settle(card, [99, 5, 3, 4])
        self.assertEqual(san, 7)
        self.assertEqual(card["current_san"], 72)

    def test_san_reward_clamped_to_max(self):
        card = _coc_card(current_san=96, skills={"侦察": {"base": 95}})
        growth.mark(card, "侦察")
        _, san = self._settle(card, [99, 6, 5, 6])
        self.assertLessEqual(card["current_san"], 99)
        self.assertEqual(card["current_san"], clamp(96 + san, 99))

    def test_no_reward_below_ninety(self):
        card = _coc_card()
        growth.mark(card, "侦察")
        _, san = self._settle(card, [90, 4])
        self.assertEqual(san, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestNoGrowthSkills(unittest.TestCase):
    """规则 5.11：克苏鲁神话与信用评级永远不会获得成长标记，也不参与 90% 理智奖励。"""

    def _card(self, **over):
        card = {"rules": "coc7th", "edu_score": 70, "dex_score": 50, "cthulhu_mythos": 0,
                "skills": {"信用评级": {"base": 0, "occupation": 95}, "侦察": {"base": 25}}}
        card.update(over)
        return card

    def test_mark_refused(self):
        card = self._card()
        self.assertFalse(growth.mark(card, "信用评级"))
        self.assertFalse(growth.mark(card, "克苏鲁神话"))
        self.assertFalse(card["skills"]["信用评级"].get("check"))
        self.assertTrue(growth.mark(card, "侦察"))

    def test_settle_skips_them(self):
        card = self._card()
        card["skills"]["信用评级"]["check"] = True     # 模拟旧数据带了勾
        card["skills"]["克苏鲁神话"] = {"base": 0, "check": True}
        with patch("core.trpg.growth.random.randint", return_value=99):
            details, _ = growth.settle(card)
        self.assertEqual([item[0] for item in details], [])
        self.assertFalse(card["skills"]["信用评级"].get("check"))
        self.assertFalse(card["skills"]["克苏鲁神话"].get("check"))
        self.assertEqual(int(card["skills"]["信用评级"].get("growth") or 0), 0)

    def test_high_credit_does_not_grant_san(self):
        card = self._card()
        card["skills"]["侦察"]["check"] = True
        # 侦察 25 → 掷 99 增长 5 点到 30，天花板仍远低于 90；信用评级 95 不该触发奖励
        with patch("core.trpg.growth.random.randint", side_effect=[99, 5]):
            _, san_change = growth.settle(card)
        self.assertEqual(san_change, 0)
        self.assertNotIn("current_san", card)

    def test_real_mastery_grants_san(self):
        card = self._card(skills={"侦察": {"base": 25, "growth": 70, "check": True}})
        with patch("core.trpg.growth.random.randint", side_effect=[99, 5, 3, 4]):
            _, san_change = growth.settle(card)
        self.assertEqual(san_change, 7)      # 2D6 = 3+4
        self.assertGreaterEqual(int(card["current_san"]), 0)
