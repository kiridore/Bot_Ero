"""卡合法性：点数超预算仍可保存，但不能设为当前角色 / 参加跑团。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.trpg import coc


def _card(**over):
    card = {
        "rules": "coc7th", "char_name": "田宫真莉", "occupation": "猎人",
        "str_score": 50, "con_score": 50, "siz_score": 50, "dex_score": 50,
        "app_score": 50, "int_score": 50, "pow_score": 50, "edu_score": 50,
        "skills": {
            "信用评级": {"base": 0, "growth": 0, "occupation": 30, "interest": 0},
            "侦察": {"base": 25, "occupation": 50},
        },
        "weapons": [], "inventory": [], "assets": {"currency": "JPY"},
        "social_background": {},
    }
    card.update(over)
    return card


class TestBudgetProblems(unittest.TestCase):
    def test_within_budget(self):
        self.assertEqual(coc.legality_problems(_card()), [])

    def test_occupation_overrun_is_not_a_save_error(self):
        card = _card(skills={"信用评级": {"occupation": 30}, "侦察": {"base": 25, "occupation": 500}})
        self.assertEqual([p for p in coc.validate(card) if "预算" in p], [])
        problems = coc.legality_problems(card)
        self.assertTrue(any("职业点超出预算" in p for p in problems), problems)

    def test_interest_overrun(self):
        card = _card(skills={"信用评级": {"occupation": 30}, "侦察": {"base": 25, "interest": 300}})
        problems = coc.legality_problems(card)
        self.assertTrue(any("兴趣点超出预算" in p for p in problems), problems)
        self.assertEqual([p for p in coc.validate(card) if "预算" in p], [])

    def test_no_occupation_with_points(self):
        card = _card(occupation="", skills={"侦察": {"base": 25, "occupation": 10}})
        problems = coc.legality_problems(card)
        self.assertTrue(any("未选择职业" in p for p in problems), problems)

    def test_dnd_card_has_no_legality_rules(self):
        self.assertEqual(coc.legality_problems({"rules": "dnd5e"}), [])
