"""COC 7th 建卡口径：派生值、技能点预算、校验与人物卡文本。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.trpg import coc


def _card(**over):
    base = {
        "rules": "coc7th",
        "char_name": "田宫真莉",
        "occupation": "药剂师",
        "age": 28,
        "str_score": 60, "con_score": 55, "siz_score": 45, "dex_score": 55,
        "app_score": 60, "int_score": 85, "pow_score": 65, "edu_score": 45,
        "luck": 50, "credit_rating": 40,
        "skills": {
            "侦查": {"base": 25, "occupation": 20},
            "聆听": {"base": 20, "interest": 10},
            "技艺:摄影": {"base": 5, "occupation": 5},
        },
    }
    base.update(over)
    return base


class TestDerived(unittest.TestCase):
    def test_hp_mp_san(self):
        fin = coc.finalize(_card())
        self.assertEqual(fin["hp"], (55 + 45) // 10)
        self.assertEqual(fin["mp"], 65 // 5)
        self.assertEqual(fin["san"], 65)

    def test_mov_and_age_penalty(self):
        self.assertEqual(coc.base_mov(60, 55, 45), 9)
        self.assertEqual(coc.base_mov(40, 45, 60), 7)
        self.assertEqual(coc.base_mov(60, 45, 60), 8)
        self.assertEqual(coc.age_mov_penalty(39), 0)
        self.assertEqual(coc.age_mov_penalty(42), 1)
        self.assertEqual(coc.age_mov_penalty(85), 5)
        self.assertEqual(coc.finalize(_card(age=42))["mov"], 8)

    def test_db_build_table(self):
        self.assertEqual(coc.db_build(64), (-2, -2))
        self.assertEqual(coc.db_build(65), (-1, -1))
        self.assertEqual(coc.db_build(85), (0, 0))
        self.assertEqual(coc.db_build(125), ("+1D4", 1))
        self.assertEqual(coc.db_build(165), ("+1D6", 2))
        self.assertEqual(coc.db_build(205), ("+2D6", 3))
        self.assertEqual(coc.db_build(285), ("+3D6", 4))

    def test_dodge_and_skill_total(self):
        fin = coc.finalize(_card())
        self.assertEqual(fin["dodge"], 27)
        self.assertEqual(fin["skills"]["侦查"]["total"], 45)
        self.assertEqual(fin["skills"]["聆听"]["total"], 30)
        self.assertEqual(fin["skills"]["技艺:摄影"]["total"], 10)

    def test_growth_may_exceed_100(self):
        # 7 版：幕间成长可以让技能超过 100%
        fin = coc.finalize(_card(skills={"侦查": {"base": 90, "growth": 20}}))
        self.assertEqual(fin["skills"]["侦查"]["total"], 110)

    def test_skill_ceiling(self):
        fin = coc.finalize(_card(skills={"侦查": {"base": 90, "growth": 500}}))
        self.assertEqual(fin["skills"]["侦查"]["total"], coc.SKILL_CEILING)


class TestBuilderScript(unittest.TestCase):
    """建卡页脚本的静态守卫：这类页面没有 DOM 测试，用源码断言挡住关键回归。"""

    def test_roll_all_includes_luck(self):
        src = (PROJECT_ROOT / "webapp" / "static" / "trpg_coc.js").read_text(encoding="utf-8")
        start = src.index('document.getElementById("rollAll").addEventListener')
        block = src[start:start + 500]
        self.assertIn("luck", block, "「全部重掷」必须同时重掷幸运")

    def test_no_dead_roll_helper(self):
        src = (PROJECT_ROOT / "webapp" / "static" / "trpg_coc.js").read_text(encoding="utf-8")
        self.assertNotIn("rollDieReady", src)


class TestBudgets(unittest.TestCase):
    def test_formula_variants(self):
        card = _card()
        self.assertEqual(coc.points_budget("教育×4", card), 180)
        self.assertEqual(coc.points_budget("教育×2＋敏捷×2", card), 200)
        self.assertEqual(coc.points_budget("教育×2＋力量或敏捷×2", card), 210)

    def test_budget_uses_occupation(self):
        fin = coc.finalize(_card())
        self.assertEqual(fin["occupation_budget"], 180)
        self.assertEqual(fin["interest_budget"], 170)
        self.assertEqual(fin["occupation_spent"], 25)

    def test_validate_over_budget(self):
        problems = coc.validate(_card(skills={"侦查": {"base": 25, "occupation": 200}}))
        self.assertTrue(any("职业点超出" in p for p in problems))

    def test_validate_interest_over_budget(self):
        problems = coc.validate(_card(skills={"侦查": {"base": 25, "interest": 200}}))
        self.assertTrue(any("兴趣点超出" in p for p in problems))

    def test_validate_credit_range(self):
        problems = coc.validate(_card(credit_rating=99))
        self.assertTrue(any("信用评级应在" in p for p in problems))

    def test_validate_requires_occupation(self):
        problems = coc.validate(_card(occupation=""))
        self.assertIn("请选择职业", problems)

    def test_valid_card_has_no_problem(self):
        self.assertEqual(coc.validate(_card()), [])


class TestSkillLookup(unittest.TestCase):
    def test_exact_and_prefix(self):
        card = _card()
        self.assertEqual(coc.skill_value(card, "侦查"), 45)
        self.assertEqual(coc.skill_value(card, "技艺:摄影"), 10)
        self.assertEqual(coc.skill_value(card, "技艺"), 10)
        self.assertIsNone(coc.skill_value(card, "驾驶"))

    def test_format_sheet(self):
        text = coc.format_sheet(_card())
        self.assertIn("药剂师", text)
        self.assertIn("HP 10", text)
        self.assertIn("MOV 9", text)
        self.assertIn("侦查 45%", text)
        self.assertNotIn("会计", text)  # 基础值技能不列出


if __name__ == "__main__":
    unittest.main(verbosity=2)
