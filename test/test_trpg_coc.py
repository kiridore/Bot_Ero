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
            # 药剂师：图书馆使用是固定本职技能，科学:化学属于可选池
            "图书馆使用": {"base": 20, "occupation": 20},
            "聆听": {"base": 20, "interest": 10},
            "科学:化学": {"base": 1, "occupation": 5},
        },
        "occupation_choices": {"1": ["科学:化学"]},
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
        self.assertEqual(fin["skills"]["图书馆使用"]["total"], 40)
        self.assertEqual(fin["skills"]["聆听"]["total"], 30)
        self.assertEqual(fin["skills"]["科学:化学"]["total"], 6)

    def test_growth_may_exceed_100(self):
        # 7 版：幕间成长可以让技能超过 100%
        fin = coc.finalize(_card(skills={"图书馆使用": {"base": 90, "growth": 20}}))
        self.assertEqual(fin["skills"]["图书馆使用"]["total"], 110)

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

    def test_pool_single_choice_uses_radio(self):
        src = (PROJECT_ROOT / "webapp" / "static" / "trpg_coc.js").read_text(encoding="utf-8")
        self.assertIn('input.type = single ? "radio" : "checkbox";', src)
        self.assertIn("const single = choice.count === 1;", src)

    def test_choice_warning_toggles_class(self):
        src = (PROJECT_ROOT / "webapp" / "static" / "trpg_coc.js").read_text(encoding="utf-8")
        self.assertIn("coc-choice-warn-on", src)
        self.assertIn("多选了", src)

    def test_occupation_fills_required_skills(self):
        src = (PROJECT_ROOT / "webapp" / "static" / "trpg_coc.js").read_text(encoding="utf-8")
        # 选职业后必须把固定本职技能补进技能表，并在换职业时撤掉未使用的自动行
        self.assertIn("const added = fillRequiredSkills(occ);", src)
        self.assertIn("pruneAutoAdded();", src)
        self.assertIn("function fillRequiredSkills(occ)", src)

    def test_add_skill_uses_inline_input(self):
        src = (PROJECT_ROOT / "webapp" / "static" / "trpg_coc.js").read_text(encoding="utf-8")
        self.assertNotIn("prompt(", src)
        self.assertIn('id="skillName"', src)
        self.assertIn('list="skillOptions"', src)
        self.assertIn("addSkillFromInput", src)
        # 定义必须真的落地，否则 bind() 里会抛 skillInput is not defined
        self.assertIn("const skillInput = document.getElementById(\"skillName\");", src)
        self.assertIn("const skillHint = document.getElementById(\"skillAddHint\");", src)
        self.assertIn("const setSkillHint = (text) =>", src)
        self.assertIn("function addSkillFromInput()", src)

    def test_non_occ_rows_disable_occ_column(self):
        src = (PROJECT_ROOT / "webapp" / "static" / "trpg_coc.js").read_text(encoding="utf-8")
        self.assertIn("occInput.disabled = !allowed;", src)
        self.assertIn("is-not-occ", src)
        self.assertIn("data-occ]:disabled", (PROJECT_ROOT / "webapp" / "static" / "trpg.css").read_text(encoding="utf-8"))

    def test_no_dead_roll_helper(self):
        src = (PROJECT_ROOT / "webapp" / "static" / "trpg_coc.js").read_text(encoding="utf-8")
        self.assertNotIn("rollDieReady", src)


class TestWeapons(unittest.TestCase):
    """武器表：保留自由文本，但校验可解析性与基础范围。"""

    def _problems(self, weapons):
        # 「使用技能」现在是必填项；这些用例只针对其它字段，统一补一个合法默认值
        return coc.weapon_problems([dict({"skill": "斗殴"}, **w) for w in weapons])

    def test_sheet_style_weapons_pass(self):
        weapons = [
            {"name": "徒手格斗", "success": 25, "damage": "1D3+DB", "range": "—",
             "attacks": "1", "ammo": "—", "malfunction": "—", "pierce": "—"},
            {"name": ".32 自动手枪", "success": 40, "damage": "1D8", "range": "15m",
             "attacks": "1(3)", "ammo": "8", "malfunction": "98", "pierce": "—"},
            {"name": "矛", "success": 20, "damage": "1D10+1D4"},
        ]
        self.assertEqual(self._problems(weapons), [])

    def test_damage_forms(self):
        for damage in ("1D6", "2d10", "1D8+2", "1D3+DB", "DB", "0", "—", ""):
            self.assertEqual(self._problems([{"name": "剑", "damage": damage}]), [], damage)

    def test_damage_rejects_garbage(self):
        for damage in ("一点八", "D", "1D", "abc", "1D8+", "+1D8", "1D0", "21D6"):
            self.assertTrue(self._problems([{"name": "剑", "damage": damage}]), damage)

    def test_empty_name_rejected(self):
        problems = self._problems([{"name": "  ", "damage": "1D6"}])
        self.assertTrue(any("缺少名称" in p for p in problems), problems)

    def test_duplicate_name_rejected(self):
        problems = self._problems([{"name": "剑", "damage": "1D8"}, {"name": " 剑 ", "damage": "1D6"}])
        self.assertTrue(any("重复添加" in p for p in problems), problems)

    def test_long_name_rejected(self):
        problems = self._problems([{"name": "剑" * 31, "damage": "1D8"}])
        self.assertTrue(any("名称过长" in p for p in problems), problems)

    def test_success_range(self):
        self.assertTrue(self._problems([{"name": "枪", "success": 999}]))
        self.assertTrue(self._problems([{"name": "枪", "success": -1}]))
        self.assertEqual(self._problems([{"name": "枪", "success": 99}]), [])

    def test_malfunction_range(self):
        self.assertTrue(self._problems([{"name": "枪", "malfunction": "abc"}]))
        self.assertTrue(self._problems([{"name": "枪", "malfunction": 101}]))
        self.assertEqual(self._problems([{"name": "枪", "malfunction": "96"}]), [])

    def test_attacks_format(self):
        self.assertEqual(self._problems([{"name": "枪", "attacks": "1(3)"}]), [])
        self.assertTrue(self._problems([{"name": "枪", "attacks": "三连发"}]))

    def test_row_limit(self):
        problems = self._problems([{"name": f"枪{i}", "damage": "1D8"} for i in range(51)])
        self.assertTrue(any("最多 50 行" in p for p in problems), problems)

    def test_field_length_limits(self):
        self.assertTrue(self._problems([{"name": "枪", "range": "很" * 21}]))
        self.assertTrue(self._problems([{"name": "枪", "ammo": "9" * 11}]))

    def test_skill_required(self):
        problems = coc.weapon_problems([{"name": "剑", "damage": "1D8"}])
        self.assertTrue(any("缺少使用技能" in p for p in problems), problems)

    def test_skill_must_exist(self):
        problems = coc.weapon_problems([{"name": "剑", "skill": "飞天", "damage": "1D8"}])
        self.assertTrue(any("不在技能表里" in p for p in problems), problems)
        for ok in ("斗殴", "手枪", "步枪/霰弹枪", "弓", "投掷", "射击:手枪", "格斗:斗殴"):
            self.assertEqual(coc.weapon_problems([{"name": "剑", "skill": ok, "damage": "1D8"}]), [], ok)

    def test_type_length(self):
        problems = coc.weapon_problems([{"name": "剑", "skill": "斗殴", "type": "类型" * 6}])
        self.assertTrue(any("类型过长" in p for p in problems), problems)

    def test_weapon_library_passes_validation(self):
        from core.trpg.weapon_data import WEAPONS
        self.assertGreaterEqual(len(WEAPONS), 100)
        for weapon in WEAPONS:
            row = {"name": weapon["name"], "skill": weapon["skill"], "type": weapon["type"],
                   "damage": weapon["damage"], "range": weapon["range"], "attacks": weapon["attacks"],
                   "ammo": weapon["capacity"], "malfunction": weapon["malfunction"],
                   "pierce": weapon["pierce"]}
            self.assertEqual(coc.weapon_problems([row]), [], weapon["name"])

    def test_damage_with_db_annotation(self):
        self.assertEqual(coc.damage_with_db("1D6+DB", "1D4"), "1D6+DB（当前 DB=1D4）")
        self.assertEqual(coc.damage_with_db("1D3+半DB", "0"), "1D3+半DB（当前 DB=0）")
        self.assertEqual(coc.damage_with_db("2D8", "1D4"), "2D8")

    def test_validate_includes_weapons(self):
        card = _card(weapons=[{"name": "剑", "damage": "一点八"}])
        self.assertTrue(any("不是合法写法" in p for p in coc.validate(card)))


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
        problems = coc.validate(_card(skills={"图书馆使用": {"base": 25, "occupation": 200}}))
        self.assertTrue(any("职业点超出" in p for p in problems))

    def test_validate_interest_over_budget(self):
        problems = coc.validate(_card(skills={"图书馆使用": {"base": 25, "interest": 200}}))
        self.assertTrue(any("兴趣点超出" in p for p in problems))

    def test_validate_credit_range(self):
        problems = coc.validate(_card(credit_rating=99))
        self.assertTrue(any("信用评级应在" in p for p in problems))

    def test_validate_allows_missing_occupation(self):
        # 未选职业也能保存：规则上技能仍有基础值
        card = _card(occupation="", occupation_choices={},
                     skills={"图书馆使用": {"base": 20}, "聆听": {"base": 20, "interest": 10}})
        self.assertEqual(coc.validate(card), [])

    def test_validate_rejects_occupation_points_without_occupation(self):
        card = _card(occupation="", occupation_choices={},
                     skills={"图书馆使用": {"base": 20, "occupation": 10}})
        self.assertTrue(any("未选择职业时不能分配职业点" in p for p in coc.validate(card)))

    def test_valid_card_has_no_problem(self):
        self.assertEqual(coc.validate(_card()), [])


class TestSkillLookup(unittest.TestCase):
    def test_exact_and_prefix(self):
        card = _card()
        self.assertEqual(coc.skill_value(card, "图书馆"), 40)
        self.assertEqual(coc.skill_value(card, "科学:化学"), 6)
        self.assertEqual(coc.skill_value(card, "科学"), 6)
        # 汽车驾驶 不在卡上，但规则默认值 20 应当可用
        self.assertEqual(coc.skill_value(card, "驾驶"), 20)
        self.assertIsNone(coc.skill_value(card, "飞天"))

    def test_format_sheet(self):
        text = coc.format_sheet(_card())
        self.assertIn("药剂师", text)
        self.assertIn("HP 10", text)
        self.assertIn("MOV 9", text)
        self.assertIn("图书馆使用 40%", text)
        self.assertNotIn("会计", text)  # 基础值技能不列出


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestSkillDefaults(unittest.TestCase):
    """规则默认值：卡上没写的标准技能也有基础成功率；闪避按 DEX/2。"""

    def test_skill_defaults_table(self):
        defaults = coc.skill_defaults(55)
        self.assertEqual(defaults["会计"], 5)
        self.assertEqual(defaults["侦察"], 25)
        self.assertEqual(defaults["急救"], 30)
        self.assertEqual(defaults["闪避"], 27)   # DEX 55 // 2

    def test_finalize_includes_all_standard_skills(self):
        fin = coc.finalize(_card(skills={}))
        # 39 项标准技能 + 由属性派生的「母语」
        self.assertEqual(len(fin["skills"]), len(coc.SKILL_BASE) + 1)
        self.assertEqual(fin["skills"]["急救"]["total"], 30)

    def test_stored_skill_overrides_default(self):
        fin = coc.finalize(_card(skills={"急救": {"base": 30, "interest": 10}}))
        self.assertEqual(fin["skills"]["急救"]["total"], 40)

    def test_dodge_uses_dex_not_stored_base(self):
        fin = coc.finalize(_card(skills={"闪避": {"base": 0}}))
        self.assertEqual(fin["skills"]["闪避"]["base"], 27)
        fin = coc.finalize(_card(skills={"闪避": {"base": 5}}, dex_score=80))
        self.assertEqual(fin["skills"]["闪避"]["base"], 40)

    def test_unknown_skill_still_missing(self):
        self.assertIsNone(coc.skill_value(_card(), "飞天"))


class TestWeaponsAfterDefaults(unittest.TestCase):
    def test_weapon_skill_base_available(self):
        # 斗殴不在 39 项标准技能里，但按武器技能表兜底（1.80.2 起）
        self.assertEqual(coc.skill_value(_card(), "斗殴"), 25)


class TestAssets(unittest.TestCase):
    """资产栏：6 档生活水平、币种、按 CR 查参考值、其他资产表校验。"""

    def test_level_for_credit(self):
        for credit, level in ((0, "身无分文"), (1, "拮据"), (9, "拮据"), (10, "标准"),
                              (49, "标准"), (50, "小康"), (89, "小康"), (90, "富裕"),
                              (98, "富裕"), (99, "富豪")):
            self.assertEqual(coc.level_for_credit(credit), level, credit)

    def test_reference_jpy(self):
        data = coc.asset_reference("JPY", 30)
        self.assertEqual(data["level"], "标准")
        self.assertEqual(data["cash"], 120000)     # CR 30 × 4000
        self.assertEqual(data["other"], 4500000)   # CR 30 × 15万
        self.assertEqual(data["spending"], 25000)

    def test_reference_flat_bracket(self):
        data = coc.asset_reference("JPY", 99)
        self.assertEqual(data["cash"], 30000000)
        self.assertEqual(data["other"], 30000000000)

    def test_reference_text_bracket(self):
        data = coc.asset_reference("GBP", 10)
        self.assertEqual(data["cash"], 100)
        self.assertEqual(data["spending"], "2镑10先令")

    def test_reference_unknown_currency(self):
        self.assertIsNone(coc.asset_reference("XXX", 30))

    def test_reference_explicit_level(self):
        data = coc.asset_reference("CNY", 30, level="富裕")
        self.assertEqual(data["level"], "富裕")
        self.assertEqual(data["cash"], 90000)      # CR 30 × 3000

    def test_asset_problems(self):
        self.assertEqual(coc.asset_problems({"currency": "JPY", "living_standard": "标准", "vehicle": 5}), [])
        self.assertTrue(any("未知币种" in p for p in coc.asset_problems({"currency": "XXX"})))
        self.assertTrue(any("不在 6 档" in p for p in coc.asset_problems({"living_standard": "贫穷"})))
        self.assertTrue(any("必须是整数" in p for p in coc.asset_problems({"vehicle": "很多"})))
        self.assertTrue(any("应在 0-" in p for p in coc.asset_problems({"vehicle": -1})))

    def test_validate_includes_assets(self):
        card = _card(assets={"currency": "XXX"})
        self.assertTrue(any("未知币种" in p for p in coc.validate(card)))

    def test_sheet_shows_assets(self):
        card = _card(assets={"currency": "JPY", "living_standard": "标准",
                             "cash": "120000", "other_assets": "都市公寓"})
        text = coc.format_sheet(card)
        self.assertIn("资产：", text)
        self.assertIn("日元（JPY）", text)
        self.assertIn("现金 120000", text)


class TestSkillNotes(unittest.TestCase):
    """技能说明：附表 B95:K212 的注释，按角色卡规范名建索引。"""

    def test_index_covers_base_skills(self):
        index = coc.skill_note_index()
        from core.trpg.coc_data import SKILL_BASE
        missing = [name for name in SKILL_BASE if name not in index]
        self.assertEqual(missing, [], missing)

    def test_alias_names_resolved(self):
        index = coc.skill_note_index()
        for canon in ("魅惑", "侦察", "领航", "计算机使用 Ω"):
            self.assertIn(canon, index, canon)
            self.assertTrue(index[canon]["note"], canon)

    def test_specialty_notes(self):
        index = coc.skill_note_index()
        self.assertIn("技艺:表演", index)
        self.assertIn("科学:化学", index)
        self.assertIn("技艺", index)     # 艺术与手艺 → 技艺

    def test_note_shape(self):
        note = coc.skill_note_index()["会计"]
        self.assertEqual(note["base"], "5%")
        self.assertTrue(note["note"].startswith("·"))


class TestWeaponSkills(unittest.TestCase):
    """武器技能（斗殴/手枪/…）不在 39 项标准技能里，但要有基础值与成长标记。"""

    def test_weapon_skill_base_table(self):
        table = coc.weapon_skill_base()
        self.assertEqual(table["斗殴"], 25)
        self.assertEqual(table["手枪"], 20)
        self.assertEqual(table["步枪/霰弹枪"], 25)
        self.assertEqual(table["弓"], 15)
        self.assertEqual(table["绞具"], 15)
        self.assertGreaterEqual(len(table), 15)

    def test_skill_value_falls_back_to_weapon_base(self):
        card = _card(skills={})
        self.assertEqual(coc.skill_value(card, "斗殴"), 25)
        self.assertEqual(coc.skill_value(card, "弓术"), 15)   # 附表写作弓术
        self.assertIsNone(coc.skill_value(card, "飞天"))

    def test_weapon_skill_marks_growth(self):
        from core.trpg import growth
        card = _card(skills={})
        self.assertTrue(growth.mark(card, "斗殴"))
        self.assertEqual(coc.finalize(card)["skills"]["斗殴"]["total"], 25)

    def test_skill_name_ok_accepts_weapon_skill(self):
        self.assertTrue(coc.skill_name_ok("斗殴"))
        self.assertTrue(coc.skill_name_ok("手枪"))
        self.assertFalse(coc.skill_name_ok("飞天"))


class TestGrowthMarkDefaults(unittest.TestCase):
    """卡上没有的技能行也应能打成长标记（1.79.0 的默认技能兜底带出的缺口）。"""

    def test_marks_unstored_standard_skill(self):
        from core.trpg import growth
        card = _card(skills={})
        self.assertTrue(growth.mark(card, "会计"))
        self.assertTrue(card["skills"]["会计"]["check"])
        self.assertEqual(coc.finalize(card)["skills"]["会计"]["total"], 5)

    def test_marks_specialty_with_sheet_base(self):
        from core.trpg import growth
        card = _card(skills={})
        self.assertTrue(growth.mark(card, "科学:化学"))
        self.assertEqual(card["skills"]["科学:化学"]["base"], 1)

    def test_alias_still_resolves_existing_row(self):
        from core.trpg import growth
        card = _card(skills={"侦察": {"base": 25}})
        self.assertTrue(growth.mark(card, "侦查"))
        self.assertTrue(card["skills"]["侦察"]["check"])
        self.assertEqual(len(card["skills"]), 1)

    def test_unknown_skill_rejected(self):
        from core.trpg import growth
        card = _card(skills={})
        self.assertFalse(growth.mark(card, "飞天"))
        self.assertEqual(card["skills"], {})


class TestSkillBaseConsistency(unittest.TestCase):
    """技能基础值只能有一个来源：标准技能、专攻、武器技能都必须查同一张表。"""

    def test_map_covers_three_kinds(self):
        table = coc.skill_base_map()
        self.assertEqual(table["会计"], 5)        # 标准技能
        self.assertEqual(table["科学:化学"], 1)    # 附表专攻
        self.assertEqual(table["斗殴"], 25)        # 武器技能
        self.assertGreaterEqual(len(table), 100)

    def test_finalize_uses_same_table(self):
        for name in ("会计", "科学:化学", "技艺:表演", "斗殴", "手枪"):
            base = coc.finalize({"rules": "coc7th", "skills": {name: {}}})["skills"][name]["base"]
            self.assertEqual(base, coc.skill_base_map()[name], name)

    def test_growth_mark_uses_same_table(self):
        from core.trpg import growth
        for name in ("科学:化学", "技艺:表演", "斗殴"):
            card = {"rules": "coc7th", "skills": {}}
            self.assertTrue(growth.mark(card, name))
            self.assertEqual(card["skills"][name]["base"], coc.skill_base_map()[name], name)

    def test_default_skills_are_standard_only(self):
        names = coc.default_skill_names()
        self.assertEqual(len(names), 39)
        self.assertIn("会计", names)
        self.assertNotIn("科学:化学", names)
        self.assertNotIn("斗殴", names)

    def test_dodge_still_derived(self):
        self.assertEqual(coc.skill_defaults(55)["闪避"], 27)


class TestDynamicBases(unittest.TestCase):
    """动态基础值：闪避 = DEX/2、母语 = EDU，随属性变化且不写死。"""

    def test_dynamic_table(self):
        card = {"rules": "coc7th", "dex_score": 55, "edu_score": 70}
        self.assertEqual(coc.skill_base_for("闪避", card), 27)
        self.assertEqual(coc.skill_base_for("母语", card), 70)
        self.assertEqual(coc.skill_base_for("会计", card), 5)

    def test_finalize_derives_and_ignores_stored(self):
        card = _card(skills={"闪避": {"base": 0}, "母语": {"base": 5}}, dex_score=80, edu_score=45)
        fin = coc.finalize(card)
        self.assertEqual(fin["skills"]["闪避"]["base"], 40)
        self.assertEqual(fin["skills"]["母语"]["base"], 45)

    def test_growth_mark_uses_dynamic_value(self):
        from core.trpg import growth
        card = {"rules": "coc7th", "dex_score": 60, "edu_score": 80, "skills": {}}
        self.assertTrue(growth.mark(card, "母语"))
        self.assertEqual(card["skills"]["母语"]["base"], 80)

    def test_skill_defaults_include_mother_tongue(self):
        defaults = coc.skill_defaults(55, 70)
        self.assertEqual(defaults["闪避"], 27)
        self.assertEqual(defaults["母语"], 70)

    def test_trailing_colon_notes_normalized(self):
        table = coc.skill_base_map()
        self.assertNotIn("学识：", table)
        self.assertNotIn("生存：", table)
        self.assertEqual(table.get("学识"), 1)
        self.assertEqual(table.get("生存"), 10)

    def test_notes_index_handles_colon_keys(self):
        index = coc.skill_note_index()
        self.assertIn("学识：", index)      # 原始键仍在（说明图标按原名查）
        self.assertEqual(coc.skill_base_for("学识"), 1)


class TestInventory(unittest.TestCase):
    """随身物品：三态、名称必填不重名、背包格范围、QQ 摘要。"""

    def test_valid_items(self):
        items = [{"status": "装备", "slot": "躯干", "name": "防弹背心", "slots": 2},
                 {"status": "携带", "name": "短管霰弹枪", "slots": "3"}]
        self.assertEqual(coc.inventory_problems(items), [])

    def test_name_required(self):
        self.assertTrue(any("缺少名称" in p for p in coc.inventory_problems([{"name": "  "}])))

    def test_duplicate_name(self):
        problems = coc.inventory_problems([{"name": "手电"}, {"name": " 手电 "}])
        self.assertTrue(any("重复添加" in p for p in problems), problems)

    def test_status_enum(self):
        problems = coc.inventory_problems([{"name": "手电", "status": "乱填"}])
        self.assertTrue(any("不在 装备/携带/背包 之内" in p for p in problems), problems)
        for status in coc.INVENTORY_STATUSES:
            self.assertEqual(coc.inventory_problems([{"name": "手电", "status": status}]), [], status)

    def test_slots_range(self):
        self.assertTrue(any("必须是整数" in p for p in coc.inventory_problems([{"name": "x", "slots": "多"}])))
        self.assertTrue(any("应在 0-20" in p for p in coc.inventory_problems([{"name": "x", "slots": 99}])))
        self.assertEqual(coc.inventory_problems([{"name": "x", "slots": 0}]), [])

    def test_row_limit(self):
        items = [{"name": f"物品{i}"} for i in range(41)]
        self.assertTrue(any("最多 40 行" in p for p in coc.inventory_problems(items)))

    def test_summary_and_sheet(self):
        card = _card(inventory=[
            {"status": "装备", "name": "防弹背心", "slots": 2},
            {"status": "背包", "name": "急救包", "slots": 1},
        ])
        items, slots = coc.inventory_summary(card)
        self.assertEqual((len(items), slots), (2, 3))
        text = coc.format_sheet(card)
        self.assertIn("装备：防弹背心（装备）、急救包（背包）", text)
        self.assertIn("共 2 件 · 3 格", text)

    def test_sheet_truncates_after_six(self):
        card = _card(inventory=[{"status": "携带", "name": f"物品{i}", "slots": 1} for i in range(8)])
        text = coc.format_sheet(card)
        self.assertIn("… 共 8 件 · 8 格", text)

    def test_validate_includes_inventory(self):
        card = _card(inventory=[{"name": "手电", "status": "乱填"}])
        self.assertTrue(any("不在 装备/携带/背包 之内" in p for p in coc.validate(card)))
