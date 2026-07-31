"""测试 TRPG 骰子系统 (Sealdice 语法)。

运行: python test/test_trpg.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from plugins.trpg_dice.dice import parse
from plugins.trpg_dice.rolls import coc_check
from plugins.trpg_dice import TrpgPlugin
from test.helper import MockApiWrapper, make_group_message


def _sent_text(plugin) -> str:
    assert len(plugin.api.sent_messages) >= 1
    return plugin.api.sent_messages[-1][1][0]["data"]["text"]


class TestDiceParse(unittest.TestCase):
    def test_empty_rolls_d100(self):
        v, d = parse("")
        self.assertTrue(1 <= v <= 100)

    def test_simple(self):
        v, d = parse("2d6")
        self.assertTrue(2 <= v <= 12)

    def test_single_die(self):
        v, d = parse("d20")
        self.assertTrue(1 <= v <= 20)

    def test_modifier(self):
        v, d = parse("d20+5")
        self.assertTrue(6 <= v <= 25)

    def test_modifier_negative(self):
        v, d = parse("d20-2")
        self.assertTrue(-1 <= v <= 18)

    def test_percentile(self):
        v, d = parse("d%")
        self.assertTrue(1 <= v <= 100)

    def test_bonus(self):
        v, d = parse("b")
        self.assertTrue(1 <= v <= 100)

    def test_penalty(self):
        v, d = parse("p2")
        self.assertTrue(1 <= v <= 100)

    def test_advantage_keyword(self):
        v, d = parse("d20优势")
        self.assertTrue(1 <= v <= 20)
        self.assertIn("|", d)

    def test_disadvantage_keyword(self):
        v, d = parse("d20劣势")
        self.assertTrue(1 <= v <= 20)
        self.assertIn("|", d)

    def test_addition(self):
        v, d = parse("10+5")
        self.assertEqual(v, 15)

    def test_multiplication(self):
        v, d = parse("5+3*2")
        self.assertEqual(v, 11)

    def test_parens(self):
        v, d = parse("(5+3)*2")
        self.assertEqual(v, 16)

    def test_multi_roll(self):
        v, d = parse("2#d10")
        self.assertTrue(2 <= v <= 20)

    def test_invalid_expr_raises(self):
        with self.assertRaises(ValueError):
            parse("abc")


class TestCocCheck(unittest.TestCase):
    @patch("plugins.trpg_dice.rolls.random.randint", return_value=45)
    def test_regular_success(self, _):
        roll, grade = coc_check(70)
        self.assertEqual(grade, "常规成功")

    @patch("plugins.trpg_dice.rolls.random.randint", return_value=7)
    def test_extreme_success(self, _):
        roll, grade = coc_check(70)
        self.assertEqual(grade, "极限成功")

    @patch("plugins.trpg_dice.rolls.random.randint", return_value=97)
    def test_fumble(self, _):
        roll, grade = coc_check(70)
        self.assertEqual(grade, "大失败")


class TestTrpgPluginMatch(unittest.TestCase):
    def test_match_r(self):
        ctx = make_group_message(".r 2d6")
        self.assertTrue(TrpgPlugin(ctx).match("message"))

    def test_match_r_bare(self):
        ctx = make_group_message(".r")
        self.assertTrue(TrpgPlugin(ctx).match("message"))

    def test_match_r_with_reason(self):
        ctx = make_group_message(".r d20 攻击检定")
        self.assertTrue(TrpgPlugin(ctx).match("message"))

    def test_match_ra(self):
        ctx = make_group_message(".ra 70")
        self.assertTrue(TrpgPlugin(ctx).match("message"))

    def test_match_rc(self):
        ctx = make_group_message(".rc 70")
        self.assertTrue(TrpgPlugin(ctx).match("message"))

    def test_match_rh(self):
        ctx = make_group_message(".rh d20")
        self.assertTrue(TrpgPlugin(ctx).match("message"))

    def test_match_rh_bare(self):
        ctx = make_group_message(".rh")
        self.assertTrue(TrpgPlugin(ctx).match("message"))

    def test_no_match_old_format(self):
        ctx = make_group_message(".r3d6")
        self.assertFalse(TrpgPlugin(ctx).match("message"))

    def test_no_match_unknown(self):
        ctx = make_group_message("hello")
        self.assertFalse(TrpgPlugin(ctx).match("message"))


class TestTrpgPluginHandle(unittest.TestCase):
    @patch("plugins.trpg_dice.dice.random.randint", side_effect=[4, 5])
    def test_handle_r_simple(self, _):
        ctx = make_group_message(".r 2d6")
        plugin = TrpgPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        out = _sent_text(plugin)
        self.assertIn("掷出了", out)
        self.assertIn("2d6", out)
        self.assertIn("9", out)

    @patch("plugins.trpg_dice.dice.random.randint", side_effect=[4, 5, 6])
    def test_handle_r_with_reason(self, _):
        ctx = make_group_message(".r 3d6 力量检定")
        plugin = TrpgPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        out = _sent_text(plugin)
        self.assertIn("由于", out)
        self.assertIn("力量检定", out)

    @patch("plugins.trpg_dice.rolls.random.randint", return_value=45)
    def test_handle_ra(self, _):
        ctx = make_group_message(".ra 70")
        plugin = TrpgPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        out = _sent_text(plugin)
        self.assertIn("COC检定", out)
        self.assertIn("常规成功", out)

    @patch("plugins.trpg_dice.dice.random.randint", return_value=13)
    def test_handle_rc_dnd_check(self, _):
        ctx = make_group_message(".rc 15")
        plugin = TrpgPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        out = _sent_text(plugin)
        self.assertIn("检定", out)
        self.assertIn("d20+15", out)

    def test_handle_invalid_expr(self):
        ctx = make_group_message(".r abc")
        plugin = TrpgPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        out = _sent_text(plugin)
        self.assertTrue("出错" in out or "无效" in out)

    @patch("plugins.trpg_dice.dice.random.randint", return_value=42)
    def test_handle_rh_group_hint(self, _):
        ctx = make_group_message(".rh d100", user_id=1234)
        plugin = TrpgPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        # First message: group hint
        out = plugin.api.sent_messages[0][1][0]["data"]["text"]
        self.assertIn("悄悄", out)

    @patch("plugins.trpg_dice.dice.random.randint", return_value=42)
    def test_handle_rh_sends_private(self, _):
        ctx = make_group_message(".rh d100", user_id=1234)
        plugin = TrpgPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        # The group hint already consumed send_msg, the private is another
        self.assertGreaterEqual(len(plugin.api.sent_messages), 2)
        # Check we called send_private_msg
        api_calls = [(t, p) for t, p in plugin.api.sent_messages]
        self.assertTrue(any(t == "send_msg" for t, _ in api_calls))


if __name__ == "__main__":
    unittest.main(verbosity=2)
