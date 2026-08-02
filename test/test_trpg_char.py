"""测试 DND 5E 角色卡插件。

运行: python test/test_trpg_char.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from plugins.trpg_char import character as char_logic
from plugins.trpg_char import rules
from plugins.trpg_char import TrpgCharPlugin
from test.helper import MockApiWrapper, make_group_message, make_private_message


def _base_data(char_id=1, **overrides):
    data = {
        "id": char_id,
        "user_id": "111",
        "char_name": "艾伦",
        "race": "精灵",
        "class_name": "法师",
        "level": 1,
        "background": "贤者",
        "str_score": 15, "dex_score": 14, "con_score": 13,
        "int_score": 12, "wis_score": 10, "cha_score": 8,
        "proficient_skills": [], "equipment": [], "hp": 0, "ac": 0, "notes": "",
    }
    data.update(overrides)
    return data


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


class TestTrpgCharPlugin(unittest.TestCase):
    def _plugin(self, msg: str, **kw):
        ctx = make_private_message(msg, **kw)
        p = TrpgCharPlugin(ctx)
        p.api = MockApiWrapper(ctx)
        return p

    def test_match_command(self):
        ctx = make_group_message("/角色")
        self.assertTrue(TrpgCharPlugin(ctx).match("message"))
        ctx2 = make_group_message("随便什么")
        self.assertFalse(TrpgCharPlugin(ctx2).match("message"))

    def test_view_own_current(self):
        p = self._plugin("/角色 查看")
        with patch("core.character_store.get_current", return_value=_base_data()):
            p.handle()
        self.assertIn("【艾伦】", _sent_text(p))

    def test_view_without_char(self):
        p = self._plugin("/角色 查看")
        with patch("core.character_store.get_current", return_value=None):
            p.handle()
        out = _sent_text(p)
        self.assertIn("还没有角色卡", out)
        self.assertIn("/profile/trpg", out)

    def test_create_redirects_to_web(self):
        p = self._plugin("/角色 创建")
        p.handle()
        self.assertIn("/profile/trpg", _sent_text(p))

    def test_edit_redirects_to_web(self):
        p = self._plugin("/角色 编辑 hp 10")
        p.handle()
        self.assertIn("/profile/trpg", _sent_text(p))

    def test_abandon_redirects_to_web(self):
        p = self._plugin("/角色 放弃")
        p.handle()
        self.assertIn("/profile/trpg", _sent_text(p))

    def test_list(self):
        p = self._plugin("/角色 列表")
        with patch("core.character_store.list_chars", return_value=[_base_data()]), \
                patch("core.character_store.get_current", return_value=_base_data()):
            p.handle()
        out = _sent_text(p)
        self.assertIn("#1", out)
        self.assertIn("艾伦", out)
        self.assertIn("当前", out)

    def test_switch(self):
        p = self._plugin("/角色 切换 1")
        with patch("core.character_store.set_current"), \
                patch("core.character_store.get_char", return_value=_base_data()):
            p.handle()
        self.assertIn("切换为 艾伦", _sent_text(p))

    def test_switch_missing(self):
        p = self._plugin("/角色 切换 99")
        with patch("core.character_store.set_current", side_effect=ValueError("角色不存在")):
            p.handle()
        self.assertIn("角色不存在", _sent_text(p))

    def test_switch_bad_format(self):
        p = self._plugin("/角色 切换 abc")
        p.handle()
        self.assertIn("格式", _sent_text(p))

    def test_delete(self):
        p = self._plugin("/角色 删除 1")
        with patch("core.character_store.get_char", return_value=_base_data()), \
                patch("core.character_store.delete_char"):
            p.handle()
        self.assertIn("已删除角色 艾伦", _sent_text(p))

    def test_delete_missing(self):
        p = self._plugin("/角色 删除 99")
        with patch("core.character_store.get_char", return_value=None):
            p.handle()
        self.assertIn("角色不存在", _sent_text(p))


class TestDiceIntegration(unittest.TestCase):
    def setUp(self):
        self._store_patch = patch("core.character_store.get_current", return_value=_base_data())
        self._store_patch.start()

    def tearDown(self):
        self._store_patch.stop()

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
