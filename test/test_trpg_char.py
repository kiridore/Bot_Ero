"""测试 DND 5E 角色卡插件。

运行: python test/test_trpg_char.py
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from plugins.trpg_char import wizard as wiz
from plugins.trpg_char import character as char_logic
from plugins.trpg_char import rules
from plugins.trpg_char import TrpgCharPlugin
from test.helper import MockApiWrapper, make_group_message


def _sent_text(plugin) -> str:
    assert len(plugin.api.sent_messages) >= 1
    return plugin.api.sent_messages[-1][1][0]["data"]["text"]


class TestRulesData(unittest.TestCase):
    def test_races_count(self):
        self.assertEqual(len(rules.RACES), 8)

    def test_classes_count(self):
        self.assertEqual(len(rules.CLASSES), 12)

    def test_skills_count(self):
        self.assertEqual(len(rules.SKILLS), 18)

    def test_ability_modifier(self):
        self.assertEqual(rules.ability_modifier(10), 0)
        self.assertEqual(rules.ability_modifier(16), 3)
        self.assertEqual(rules.ability_modifier(8), -1)

    def test_point_buy_valid(self):
        cost = sum(rules.POINT_BUY_COST[v] for v in (15, 14, 13, 12, 10, 8))
        self.assertLessEqual(cost, rules.POINT_BUY_BUDGET)


class TestCharacterCalc(unittest.TestCase):
    def test_finalize_applies_race_bonus(self):
        char = {
            "race": "精灵", "class_name": "法师", "level": 1, "background": "贤者",
            "str_score": 15, "dex_score": 14, "con_score": 13,
            "int_score": 12, "wis_score": 10, "cha_score": 8,
            "proficient_skills": [], "equipment": [], "hp": 0, "ac": 0,
        }
        data = char_logic.finalize(char)
        self.assertEqual(data["dex_score"], 16)  # 精灵 +2 敏捷
        self.assertEqual(data["int_score"], 13)  # 精灵 +1 智力
        self.assertEqual(data["hp"], 6 + 1)      # 法师 d6 + 体质13(+1)
        self.assertEqual(data["ac"], 10 + 3)     # 敏捷16(+3)

    def test_skill_mods_with_proficiency(self):
        char = {
            "race": "人类", "class_name": "战士", "level": 1, "background": "士兵",
            "str_score": 15, "dex_score": 14, "con_score": 13,
            "int_score": 12, "wis_score": 10, "cha_score": 8,
            "proficient_skills": ["运动"], "equipment": [], "hp": 0, "ac": 0,
        }
        data = char_logic.finalize(char)
        # 人类 +1 全属性 → 力量16(+3)
        self.assertEqual(data["skill_mods"]["运动"], 3 + 2)   # STR+3 熟练+2
        self.assertEqual(data["skill_mods"]["杂技"], 2)       # DEX+2 未熟练

    def test_resolve_expression_values(self):
        char = {
            "race": "人类", "class_name": "战士", "level": 1, "background": "士兵",
            "str_score": 15, "dex_score": 14, "con_score": 13,
            "int_score": 12, "wis_score": 10, "cha_score": 8,
            "proficient_skills": ["运动"], "equipment": [], "hp": 0, "ac": 0,
        }
        values = char_logic.resolve_expression_values(char)
        self.assertEqual(values["力量"], 3)
        self.assertEqual(values["运动"], 5)


class TestWizard(unittest.TestCase):
    def _run_flow(self, replies):
        state = wiz.start()
        done, data = False, None
        for r in replies:
            m, done, data = wiz.handle_reply(state, r)
            if done:
                break
        return done, data

    def test_full_flow_point_buy(self):
        done, data = self._run_flow(
            ["1", "15 14 13 12 10 8", "奥术 历史", "艾伦 精灵 法师"]
        )
        self.assertTrue(done)
        self.assertIsNotNone(data)
        self.assertEqual(data["char_name"], "艾伦")
        self.assertEqual(data["race"], "精灵")
        self.assertEqual(data["class_name"], "法师")
        self.assertEqual(data["proficient_skills"], ["奥术", "历史"])

    def test_full_flow_standard_array_skip_skills(self):
        done, data = self._run_flow(
            ["3", "15 14 13 12 10 8", "跳过", "铁牛 人类 战士"]
        )
        self.assertTrue(done)
        self.assertEqual(data["char_name"], "铁牛")
        self.assertEqual(data["proficient_skills"], [])

    def test_full_flow_roll(self):
        import unittest.mock as mock
        with mock.patch("plugins.trpg_char.wizard._roll_scores", return_value=[15, 14, 13, 12, 10, 8]):
            done, data = self._run_flow(
                ["2", "15 14 13 12 10 8", "宗教", "铜须 矮人 牧师"]
            )
        self.assertTrue(done)
        self.assertEqual(data["char_name"], "铜须")

    def test_abandon(self):
        state = wiz.start()
        m, done, data = wiz.handle_reply(state, "退出")
        self.assertTrue(done)
        self.assertIsNone(data)

    def test_point_buy_over_budget(self):
        state = wiz.start()
        wiz.handle_reply(state, "1")
        m, done, data = wiz.handle_reply(state, "15 15 15 15 15 15")
        self.assertFalse(done)
        self.assertIn("预算", m)

    def test_custom_race_class_free_text(self):
        done, data = self._run_flow(
            ["1", "15 14 13 12 10 8", "跳过", "神秘人 天界裔 自创职业"]
        )
        self.assertTrue(done)
        self.assertEqual(data["race"], "天界裔")
        self.assertEqual(data["class_name"], "自创职业")


class TestTrpgCharPlugin(unittest.TestCase):
    def setUp(self):
        for f in ["data.db", "data.db-wal", "data.db-shm"]:
            if os.path.exists(f):
                os.remove(f)
        from core import context as runtime_context
        runtime_context.character_wizards.clear()

    def tearDown(self):
        for f in ["data.db", "data.db-wal", "data.db-shm"]:
            if os.path.exists(f):
                os.remove(f)
        from core import context as runtime_context
        runtime_context.character_wizards.clear()

    def _create_char(self, user_id=111, nickname="玩家A"):
        ctx = make_group_message("/角色 创建", user_id=user_id, nickname=nickname)
        p = TrpgCharPlugin(ctx)
        p.api = MockApiWrapper(ctx)
        p.handle()
        for s in ["1", "15 14 13 12 10 8", "奥术 历史", "艾伦 精灵 法师"]:
            ctx = make_group_message(s, user_id=user_id, nickname=nickname)
            p = TrpgCharPlugin(ctx)
            p.api = MockApiWrapper(ctx)
            p.handle()

    def test_match_command(self):
        ctx = make_group_message("/角色")
        self.assertTrue(TrpgCharPlugin(ctx).match("message"))

    def test_match_during_wizard(self):
        ctx = make_group_message("/角色 创建", user_id=111)
        p = TrpgCharPlugin(ctx)
        p.api = MockApiWrapper(ctx)
        p.handle()
        ctx2 = make_group_message("随便什么", user_id=111)
        self.assertTrue(TrpgCharPlugin(ctx2).match("message"))

    def test_create_and_view(self):
        self._create_char()
        ctx = make_group_message("/角色", user_id=111)
        p = TrpgCharPlugin(ctx)
        p.api = MockApiWrapper(ctx)
        p.handle()
        out = _sent_text(p)
        self.assertIn("艾伦", out)
        self.assertIn("法师", out)

    def test_create_while_wizard_active(self):
        ctx = make_group_message("/角色 创建", user_id=111)
        p = TrpgCharPlugin(ctx)
        p.api = MockApiWrapper(ctx)
        p.handle()
        p2 = TrpgCharPlugin(ctx)
        p2.api = MockApiWrapper(ctx)
        p2.handle()
        self.assertIn("已有进行中", _sent_text(p2))

    def test_view_no_character(self):
        ctx = make_group_message("/角色", user_id=999)
        p = TrpgCharPlugin(ctx)
        p.api = MockApiWrapper(ctx)
        p.handle()
        self.assertIn("还没有角色卡", _sent_text(p))

    def test_list_and_switch(self):
        self._create_char()
        ctx = make_group_message("/角色 列表", user_id=111)
        p = TrpgCharPlugin(ctx)
        p.api = MockApiWrapper(ctx)
        p.handle()
        out = _sent_text(p)
        self.assertIn("#1", out)
        self.assertIn("艾伦", out)

    def test_edit_hp(self):
        self._create_char()
        ctx = make_group_message("/角色 编辑 hp 10", user_id=111)
        p = TrpgCharPlugin(ctx)
        p.api = MockApiWrapper(ctx)
        p.handle()
        self.assertIn("已更新", _sent_text(p))

    def test_edit_invalid_field(self):
        self._create_char()
        ctx = make_group_message("/角色 编辑 法力 10", user_id=111)
        p = TrpgCharPlugin(ctx)
        p.api = MockApiWrapper(ctx)
        p.handle()
        self.assertIn("无法编辑", _sent_text(p))

    def test_delete_character(self):
        self._create_char()
        ctx = make_group_message("/角色 删除 1", user_id=111)
        p = TrpgCharPlugin(ctx)
        p.api = MockApiWrapper(ctx)
        p.handle()
        self.assertIn("已删除", _sent_text(p))
        ctx2 = make_group_message("/角色", user_id=111)
        p2 = TrpgCharPlugin(ctx2)
        p2.api = MockApiWrapper(ctx2)
        p2.handle()
        self.assertIn("还没有角色卡", _sent_text(p2))


class TestDiceIntegration(unittest.TestCase):
    def setUp(self):
        for f in ["data.db", "data.db-wal", "data.db-shm"]:
            if os.path.exists(f):
                os.remove(f)
        from core import context as runtime_context
        runtime_context.character_wizards.clear()
        # 直接创建角色
        from plugins.trpg_char import character as char_logic
        from test.helper import MockApiWrapper, make_group_message
        from plugins.trpg_char import TrpgCharPlugin
        ctx = make_group_message("/角色 创建", user_id=111, nickname="玩家A")
        p = TrpgCharPlugin(ctx)
        p.api = MockApiWrapper(ctx)
        p.handle()
        for s in ["1", "15 14 13 12 10 8", "奥术 历史", "艾伦 精灵 法师"]:
            ctx = make_group_message(s, user_id=111, nickname="玩家A")
            p = TrpgCharPlugin(ctx)
            p.api = MockApiWrapper(ctx)
            p.handle()

    def tearDown(self):
        for f in ["data.db", "data.db-wal", "data.db-shm"]:
            if os.path.exists(f):
                os.remove(f)
        from core import context as runtime_context
        runtime_context.character_wizards.clear()

    def test_roll_with_attribute(self):
        from plugins.trpg_dice import TrpgPlugin
        ctx = make_group_message(".r 力量+2", user_id=111, nickname="玩家A")
        p = TrpgPlugin(ctx)
        p.api = MockApiWrapper(ctx)
        p.handle()
        out = _sent_text(p)
        self.assertIn("力量+2", out)

    def test_roll_with_skill(self):
        from plugins.trpg_dice import TrpgPlugin
        ctx = make_group_message(".r 奥术", user_id=111, nickname="玩家A")
        p = TrpgPlugin(ctx)
        p.api = MockApiWrapper(ctx)
        p.handle()
        out = _sent_text(p)
        self.assertIn("奥术", out)

    def test_rc_attribute_check(self):
        from plugins.trpg_dice import TrpgPlugin
        ctx = make_group_message(".rc 力量", user_id=111, nickname="玩家A")
        p = TrpgPlugin(ctx)
        p.api = MockApiWrapper(ctx)
        p.handle()
        out = _sent_text(p)
        self.assertIn("力量检定", out)
        self.assertIn("d20+2", out)

    def test_rc_saving_throw(self):
        from plugins.trpg_dice import TrpgPlugin
        ctx = make_group_message(".rc 体质 豁免", user_id=111, nickname="玩家A")
        p = TrpgPlugin(ctx)
        p.api = MockApiWrapper(ctx)
        p.handle()
        out = _sent_text(p)
        self.assertIn("体质豁免", out)

    def test_rc_advantage(self):
        from plugins.trpg_dice import TrpgPlugin
        ctx = make_group_message(".rc 优势 力量", user_id=111, nickname="玩家A")
        p = TrpgPlugin(ctx)
        p.api = MockApiWrapper(ctx)
        p.handle()
        out = _sent_text(p)
        self.assertIn("优势", out)

    def test_rc_skill_alias(self):
        from plugins.trpg_dice import TrpgPlugin
        ctx = make_group_message(".rc 侦查", user_id=111, nickname="玩家A")
        p = TrpgPlugin(ctx)
        p.api = MockApiWrapper(ctx)
        p.handle()
        out = _sent_text(p)
        self.assertIn("侦查检定", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
