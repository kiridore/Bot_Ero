"""COC 职业点：本职属性选择（或/自定义职业第二属性）与职业数据对齐新卡。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.trpg import coc, coc_data
from core.trpg.coc_data import OCCUPATIONS


def _card(**over):
    card = {
        "rules": "coc7th", "char_name": "哈维", "occupation": "猎人",
        "str_score": 45, "con_score": 50, "siz_score": 55, "dex_score": 70,
        "app_score": 40, "int_score": 60, "pow_score": 65, "edu_score": 80,
        "skills": {},
    }
    card.update(over)
    return card


class TestFormulaOptions(unittest.TestCase):
    def test_alternative(self):
        self.assertEqual(coc.formula_options("教育×2＋力量或敏捷×2"), ["力量", "敏捷"])

    def test_no_alternative(self):
        self.assertEqual(coc.formula_options("教育×4"), [])
        self.assertEqual(coc.formula_options("教育×2＋敏捷×2"), [])


class TestBudget(unittest.TestCase):
    def test_default_takes_higher(self):
        # 教育 80×2 + max(力量 45, 敏捷 70)×2
        self.assertEqual(coc.occupation_budget(_card()), 160 + 140)

    def test_chosen_lower_attribute(self):
        self.assertEqual(coc.occupation_budget(_card(occupation_attr="力量")), 160 + 90)

    def test_chosen_higher_attribute(self):
        self.assertEqual(coc.occupation_budget(_card(occupation_attr="敏捷")), 160 + 140)

    def test_custom_occupation_blank_is_edu4(self):
        card = _card(occupation="自定义职业")
        self.assertEqual(coc.occupation_budget(card), 80 * 4)

    def test_custom_occupation_second_attribute(self):
        card = _card(occupation="自定义职业", occupation_attr="意志")
        self.assertEqual(coc.occupation_budget(card), 80 * 2 + 65 * 2)

    def test_no_occupation(self):
        self.assertEqual(coc.occupation_budget(_card(occupation="")), 0)


class TestAttrProblems(unittest.TestCase):
    def test_valid_choice(self):
        self.assertEqual(coc.occupation_attr_problems(_card(occupation_attr="力量")), [])

    def test_choice_not_in_options(self):
        problems = coc.occupation_attr_problems(_card(occupation_attr="意志"))
        self.assertTrue(any("只能选 力量、敏捷" in p for p in problems), problems)

    def test_choice_on_formula_without_alternatives(self):
        card = _card(occupation="会计师", occupation_attr="力量")
        problems = coc.occupation_attr_problems(card)
        self.assertTrue(any("没有可选项" in p for p in problems), problems)

    def test_custom_occupation_allows_eight(self):
        for attr in ("力量", "体质", "体型", "敏捷", "外貌", "智力", "意志", "教育"):
            self.assertEqual(
                coc.occupation_attr_problems(_card(occupation="自定义职业", occupation_attr=attr)), [], attr)

    def test_custom_occupation_rejects_unknown(self):
        problems = coc.occupation_attr_problems(_card(occupation="自定义职业", occupation_attr="幸运"))
        self.assertTrue(any("只能是" in p for p in problems), problems)

    def test_attr_without_occupation(self):
        problems = coc.occupation_attr_problems(_card(occupation="", occupation_attr="力量"))
        self.assertTrue(any("未选择职业" in p for p in problems), problems)

    def test_validate_blocks_bad_choice(self):
        problems = coc.validate(_card(occupation_attr="意志"))
        self.assertTrue(any("只能选 力量、敏捷" in p for p in problems), problems)


class TestOccupationData(unittest.TestCase):
    """与新卡（CY26.3 职业列表首个同名行）对齐：海员两条曾是 教育×4。"""

    def _formula(self, name):
        for _seq, job, _lo, _hi, formula, _own in OCCUPATIONS:
            if job == name:
                return formula
        raise AssertionError(name)

    def test_sailor_formulas(self):
        self.assertEqual(self._formula("海员-军舰海员"), "教育×2＋敏捷或力量×2")
        self.assertEqual(self._formula("海员-民船海员"), "教育×2＋敏捷或力量×2")

    def test_budget_matches_card_for_sailor(self):
        card = _card(occupation="海员-军舰海员")
        self.assertEqual(coc.occupation_budget(card), 160 + 140)   # 300，不是 教育×4=320

    def test_alternative_formulas_use_new_wording(self):
        self.assertEqual(self._formula("猎人"), "教育×2＋力量或敏捷×2")
        self.assertEqual(self._formula("私家侦探"), "教育×2＋力量或敏捷×2")


class TestFinalize(unittest.TestCase):
    def test_finalize_exposes_attr_and_budget(self):
        fin = coc.finalize(_card(occupation_attr="力量"))
        self.assertEqual(fin["occupation_attr"], "力量")
        self.assertEqual(fin["occupation_budget"], 250)

    def test_format_sheet_shows_choice(self):
        out = coc.format_sheet(_card(occupation_attr="力量"))
        self.assertIn("职业点 0/250（教育×2＋力量或敏捷×2，按力量）", out)
