"""跑团数值指令：.hp / .san / .sc 的边界、权限与门控。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import character_store as store
from test.helper import MockApiWrapper, make_group_message
from plugins.trpg_vitals import TrpgVitalsPlugin, roll_expression
from core.trpg import vitals
import core.context as runtime_context

GROUP_ID = 296470819
DM_ID = "111"
PLAYER_ID = "222"


def _dnd_card(**over):
    card = {
        "rules": "dnd5e", "char_name": "艾伦", "race": "人类", "class_name": "战士",
        "attributes_mode": "manual", "level": 3,
        "str_score": 15, "dex_score": 14, "con_score": 14,
        "int_score": 10, "wis_score": 10, "cha_score": 8,
        "hp": 30, "current_hp": 30,
    }
    card.update(over)
    return card


def _coc_card(**over):
    card = {
        "rules": "coc7th", "char_name": "田宫真莉", "occupation": "药剂师",
        "str_score": 60, "con_score": 55, "siz_score": 45, "dex_score": 55,
        "app_score": 60, "int_score": 85, "pow_score": 65, "edu_score": 45,
        "current_hp": 10, "current_san": 65, "cthulhu_mythos": 0,
    }
    card.update(over)
    return card


class VitalsBase(unittest.TestCase):
    rule = "dnd5e"

    def setUp(self):
        runtime_context.recording_sessions.clear()
        self.cards: dict[str, dict] = {}

    def install(self, cards: dict[str, dict]):
        for uid, card in cards.items():
            card.setdefault("id", 1)
            card.setdefault("user_id", uid)
        self.cards = cards

    def get_current(self, user_id):
        card = self.cards.get(str(user_id))
        return dict(card) if card else None

    def update_char(self, user_id, char_id, data):
        self.cards[str(user_id)].update(data)

    def invoke(self, msg, user_id=DM_ID, nickname="老张", rule=None, roles=None, roll=None, rolls=None):
        if roles is not None:
            runtime_context.recording_sessions[GROUP_ID] = {"roles": roles}
        ctx = make_group_message(msg, user_id=user_id, nickname=nickname)
        plugin = TrpgVitalsPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        patches = [
            patch("plugins.trpg_vitals.store.get_current", side_effect=self.get_current),
            patch("plugins.trpg_vitals.store.update_char", side_effect=self.update_char),
            patch("plugins.trpg_vitals.party.current_rule", return_value=rule or self.rule),
        ]
        if rolls is not None:
            patches.append(patch("plugins.trpg_vitals.random.randint", side_effect=rolls))
        elif roll is not None:
            patches.append(patch("plugins.trpg_vitals.random.randint", return_value=roll))
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        plugin.handle()
        return plugin.api.sent_messages[-1][1][0]["data"]["text"] if plugin.api.sent_messages else ""


class TestParsing(unittest.TestCase):
    def test_clamp(self):
        self.assertEqual(vitals.clamp(-5, 10), 0)
        self.assertEqual(vitals.clamp(99, 10), 10)

    def test_roll_number_and_dice(self):
        self.assertEqual(roll_expression("3"), (3, "3"))
        with patch("plugins.trpg_vitals.random.randint", return_value=4):
            self.assertEqual(roll_expression("1d6"), (4, "d6=4"))
        with patch("plugins.trpg_vitals.random.randint", return_value=3):
            self.assertEqual(roll_expression("2d6+1"), (7, "2d6=7"))

    def test_roll_rejects_bad_expression(self):
        with self.assertRaises(ValueError):
            roll_expression("abc")


class TestHp(VitalsBase):
    def test_damage(self):
        self.install({PLAYER_ID: _dnd_card(current_hp=20)})
        out = self.invoke(".hp -5", user_id=PLAYER_ID)
        self.assertIn("HP 20 → 15", out)
        self.assertEqual(self.cards[PLAYER_ID]["current_hp"], 15)

    def test_zero_hp_note(self):
        self.install({PLAYER_ID: _dnd_card(current_hp=3)})
        out = self.invoke(".hp -99", user_id=PLAYER_ID)
        self.assertIn("HP 归零", out)
        self.assertEqual(self.cards[PLAYER_ID]["current_hp"], 0)

    def test_full_restore(self):
        self.install({PLAYER_ID: _dnd_card(current_hp=4)})
        out = self.invoke(".hp 满", user_id=PLAYER_ID)
        self.assertIn("已回满", out)
        self.assertEqual(self.cards[PLAYER_ID]["current_hp"], 30)

    def test_requires_sign(self):
        self.install({PLAYER_ID: _dnd_card()})
        self.assertIn("请带上正负号", self.invoke(".hp 5", user_id=PLAYER_ID))

    def test_dice_damage(self):
        self.install({PLAYER_ID: _dnd_card(current_hp=20)})
        out = self.invoke(".hp -1d6", user_id=PLAYER_ID, roll=4)
        self.assertIn("HP 20 → 16", out)
        self.assertIn("1d6", out.replace("d6=4", "1d6"))


class TestPermissions(VitalsBase):
    def test_player_cannot_touch_other(self):
        self.install({DM_ID: _dnd_card(), PLAYER_ID: _dnd_card()})
        ctx = make_group_message(".hp -5", user_id=PLAYER_ID, nickname="小王")
        ctx["message"].append({"type": "at", "data": {"qq": DM_ID}})
        plugin = TrpgVitalsPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        with patch("plugins.trpg_vitals.store.get_current", side_effect=self.get_current),                 patch("plugins.trpg_vitals.store.update_char", side_effect=self.update_char),                 patch("plugins.trpg_vitals.party.current_rule", return_value="dnd5e"):
            plugin.handle()
        out = plugin.api.sent_messages[-1][1][0]["data"]["text"]
        self.assertIn("只有 DM", out)
        self.assertEqual(self.cards[DM_ID]["current_hp"], 30)

    def test_dm_can_target_other(self):
        self.install({DM_ID: _dnd_card(), PLAYER_ID: _dnd_card(current_hp=20)})
        runtime_context.recording_sessions[GROUP_ID] = {"roles": {DM_ID: "dm"}}
        ctx = make_group_message(".hp -5", user_id=DM_ID, nickname="老张")
        ctx["message"].append({"type": "at", "data": {"qq": PLAYER_ID}})
        plugin = TrpgVitalsPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        with patch("plugins.trpg_vitals.store.get_current", side_effect=self.get_current),                 patch("plugins.trpg_vitals.store.update_char", side_effect=self.update_char),                 patch("plugins.trpg_vitals.party.current_rule", return_value="dnd5e"):
            plugin.handle()
        self.assertEqual(self.cards[PLAYER_ID]["current_hp"], 15)


class TestRuleGate(VitalsBase):
    def test_san_refused_on_dnd_card(self):
        self.install({PLAYER_ID: _dnd_card()})
        self.assertIn("没有 SAN", self.invoke(".san -1", user_id=PLAYER_ID))

    def test_group_rule_mismatch_refused(self):
        self.install({PLAYER_ID: _dnd_card()})
        out = self.invoke(".hp -5", user_id=PLAYER_ID, rule="coc7th")
        self.assertIn("本团规则是 COC 7th", out)


class TestMp(VitalsBase):
    rule = "coc7th"

    def test_spend_mp(self):
        self.install({PLAYER_ID: _coc_card()})
        out = self.invoke(".mp -3", user_id=PLAYER_ID)
        self.assertIn("MP 13 → 10", out)
        self.assertEqual(self.cards[PLAYER_ID]["current_mp"], 10)

    def test_restore_mp(self):
        self.install({PLAYER_ID: _coc_card(current_mp=2)})
        out = self.invoke(".mp 满", user_id=PLAYER_ID)
        self.assertIn("已回满", out)
        self.assertEqual(self.cards[PLAYER_ID]["current_mp"], 13)

    def test_mp_rejected_for_dnd(self):
        self.rule = "dnd5e"
        self.install({PLAYER_ID: _dnd_card()})
        out = self.invoke(".mp -1", user_id=PLAYER_ID)
        self.assertIn("DND 5E", out)


class TestSanCheck(VitalsBase):
    rule = "coc7th"

    def test_success_deducts_success_loss(self):
        self.install({PLAYER_ID: _coc_card()})
        out = self.invoke(".sc 1/1d6", user_id=PLAYER_ID, rolls=[42])
        self.assertIn("成功", out)
        self.assertIn("SAN 65 → 64", out)
        self.assertEqual(self.cards[PLAYER_ID]["current_san"], 64)

    def test_failure_deducts_fail_loss_and_hints(self):
        self.install({PLAYER_ID: _coc_card()})
        out = self.invoke(".sc 0/1d6", user_id=PLAYER_ID, rolls=[99, 4])
        self.assertIn("失败", out)
        self.assertIn("SAN 65 → 61", out)
        self.assertIn("今日累计损失 4", out)
        self.assertNotIn("一次性损失 ≥5", out)

    def test_five_point_loss_hints_idea_roll(self):
        self.install({PLAYER_ID: _coc_card()})
        out = self.invoke(".sc 0/1d10", user_id=PLAYER_ID, rolls=[99, 6])
        self.assertIn("一次性损失 ≥5", out)

    def test_zero_loss_on_success(self):
        self.install({PLAYER_ID: _coc_card()})
        self.assertIn("SAN 65 → 65", self.invoke(".sc 0/1d6", user_id=PLAYER_ID, rolls=[10]))

    def test_san_zero_reports_permanent_madness(self):
        self.install({PLAYER_ID: _coc_card(current_san=2)})
        out = self.invoke(".sc 0/1d10", user_id=PLAYER_ID, rolls=[90, 10])
        self.assertIn("永久疯狂", out)
        self.assertEqual(self.cards[PLAYER_ID]["current_san"], 0)

    def test_daily_accumulation(self):
        self.install({PLAYER_ID: _coc_card()})
        self.invoke(".sc 0/1d6", user_id=PLAYER_ID, rolls=[99, 4])
        out = self.invoke(".sc 0/1d6", user_id=PLAYER_ID, rolls=[99, 4])
        self.assertIn("今日累计损失 8", out)
        self.assertEqual(self.cards[PLAYER_ID]["san_loss_today"], 8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
