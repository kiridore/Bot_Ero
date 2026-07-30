"""测试 TRPG 骰子系统。

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
from plugins.trpg_dice.rolls import coc_check, dnd_advantage, dnd_disadvantage, dnd_ability_scores
from plugins.trpg_dice import TrpgPlugin
from test.helper import MockApiWrapper, make_group_message


def _sent_text(plugin) -> str:
    assert len(plugin.api.sent_messages) == 1
    return plugin.api.sent_messages[0][1][0]["data"]["text"]


class TestDiceParse(unittest.TestCase):
    def test_simple(self):
        dr = parse("2d6")
        self.assertEqual(dr.count, 2)
        self.assertEqual(dr.sides, 6)

    def test_single_die(self):
        dr = parse("d20")
        self.assertEqual(dr.count, 1)
        self.assertEqual(dr.sides, 20)

    def test_modifier(self):
        dr = parse("2d6+3")
        self.assertEqual(dr.modifier, 3)

    def test_modifier_negative(self):
        dr = parse("1d20-2")
        self.assertEqual(dr.modifier, -2)

    def test_percentile(self):
        dr = parse("d%")
        self.assertEqual(dr.count, 1)
        self.assertEqual(dr.sides, 100)

    def test_fudge(self):
        dr = parse("dF")
        self.assertEqual(dr.count, 1)
        self.assertEqual(dr.sides, -1)

    def test_keep(self):
        dr = parse("4d6k3")
        self.assertEqual(dr.count, 4)
        self.assertEqual(dr.sides, 6)
        self.assertEqual(dr.keep, 3)
        self.assertFalse(dr.keep_low)

    def test_keep_low(self):
        dr = parse("4d6kl2")
        self.assertEqual(dr.keep, 2)
        self.assertTrue(dr.keep_low)

    def test_limit_exceeded(self):
        with self.assertRaises(ValueError):
            parse("200d6")

    def test_invalid_expression(self):
        with self.assertRaises(ValueError):
            parse("abc")


class TestDiceRoll(unittest.TestCase):
    def test_simple_roll(self):
        dr = parse("2d6")
        raw, total, desc = dr.roll()
        self.assertEqual(len(raw), 2)
        self.assertTrue(all(1 <= v <= 6 for v in raw))
        self.assertEqual(total, sum(raw))

    def test_modifier_roll(self):
        dr = parse("2d6+3")
        raw, total, _ = dr.roll()
        self.assertEqual(total, sum(raw) + 3)

    @patch("plugins.trpg_dice.dice.random.randint", side_effect=[6, 5, 4, 3])
    def test_keep_highest(self, _):
        dr = parse("4d6k3")
        raw, total, desc = dr.roll()
        self.assertEqual(total, 6 + 5 + 4)

    @patch("plugins.trpg_dice.dice.random.randint", side_effect=[1, 2, 3, 4])
    def test_keep_lowest(self, _):
        dr = parse("4d6kl2")
        raw, total, desc = dr.roll()
        self.assertEqual(total, 1 + 2)


class TestCocCheck(unittest.TestCase):
    @patch("plugins.trpg_dice.rolls.random.randint", return_value=45)
    def test_regular_success(self, _):
        roll, grade = coc_check(70)
        self.assertEqual(grade, "常规成功")

    @patch("plugins.trpg_dice.rolls.random.randint", return_value=20)
    def test_hard_success(self, _):
        roll, grade = coc_check(70)
        self.assertEqual(grade, "困难成功")

    @patch("plugins.trpg_dice.rolls.random.randint", return_value=7)
    def test_extreme_success(self, _):
        roll, grade = coc_check(70)
        self.assertEqual(grade, "极限成功")

    @patch("plugins.trpg_dice.rolls.random.randint", return_value=97)
    def test_fumble(self, _):
        roll, grade = coc_check(70)
        self.assertEqual(grade, "大失败")


class TestDndAdvantage(unittest.TestCase):
    @patch("plugins.trpg_dice.rolls.random.randint", side_effect=[10, 15])
    def test_advantage_takes_highest(self, _):
        rolls, best, total = dnd_advantage()
        self.assertEqual(rolls, [10, 15])
        self.assertEqual(best, 15)
        self.assertEqual(total, 15)

    @patch("plugins.trpg_dice.rolls.random.randint", side_effect=[5, 3])
    def test_disadvantage_takes_lowest(self, _):
        rolls, worst, total = dnd_disadvantage()
        self.assertEqual(rolls, [5, 3])
        self.assertEqual(worst, 3)
        self.assertEqual(total, 3)

    @patch("plugins.trpg_dice.rolls.random.randint", side_effect=[10, 15])
    def test_advantage_with_modifier(self, _):
        _, _, total = dnd_advantage(5)
        self.assertEqual(total, 20)


class TestAbilityScores(unittest.TestCase):
    def test_returns_six_scores(self):
        scores = dnd_ability_scores()
        self.assertEqual(len(scores), 6)
        for rolls, score in scores:
            self.assertEqual(len(rolls), 4)
            self.assertTrue(all(1 <= v <= 6 for v in rolls))


class TestTrpgPluginMatch(unittest.TestCase):
    def test_match_r_expression(self):
        ctx = make_group_message(".r 2d6+3")
        self.assertTrue(TrpgPlugin(ctx).match("message"))

    def test_match_ra(self):
        ctx = make_group_message(".ra d20+5")
        self.assertTrue(TrpgPlugin(ctx).match("message"))

    def test_match_rd(self):
        ctx = make_group_message(".rd d20+5")
        self.assertTrue(TrpgPlugin(ctx).match("message"))

    def test_match_rc(self):
        ctx = make_group_message(".rc 70")
        self.assertTrue(TrpgPlugin(ctx).match("message"))

    def test_match_rcb(self):
        ctx = make_group_message(".rcb 60 50")
        self.assertTrue(TrpgPlugin(ctx).match("message"))

    def test_match_rh(self):
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
        self.assertIn("合计: 9", out)

    @patch("plugins.trpg_dice.dice.random.randint", side_effect=[6, 5, 4, 3])
    def test_handle_r_keep(self, _):
        ctx = make_group_message(".r 4d6k3")
        plugin = TrpgPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        out = _sent_text(plugin)
        self.assertIn("合计: 15", out)

    @patch("plugins.trpg_dice.rolls.random.randint", return_value=45)
    def test_handle_rc(self, _):
        ctx = make_group_message(".rc 70")
        plugin = TrpgPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        out = _sent_text(plugin)
        self.assertIn("常规成功", out)

    @patch("plugins.trpg_dice.rolls.random.randint", side_effect=[15, 20])
    def test_handle_ra(self, _):
        ctx = make_group_message(".ra d20+3")
        plugin = TrpgPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        out = _sent_text(plugin)
        self.assertIn("[优势]", out)
        self.assertIn("20", out)

    @patch("plugins.trpg_dice.rolls.random.randint", side_effect=[15, 20])
    def test_handle_rd(self, _):
        ctx = make_group_message(".rd d20+3")
        plugin = TrpgPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        out = _sent_text(plugin)
        self.assertIn("[劣势]", out)
        self.assertIn("15", out)

    def test_handle_rcb(self):
        with patch("plugins.trpg_dice.rolls.random.randint", side_effect=[45, 60]):
            ctx = make_group_message(".rcb 70 50")
            plugin = TrpgPlugin(ctx)
            plugin.api = MockApiWrapper(ctx)
            plugin.handle()
            out = _sent_text(plugin)
            self.assertIn("结果:", out)

    def test_handle_rh(self):
        ctx = make_group_message(".rh")
        plugin = TrpgPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        out = _sent_text(plugin)
        self.assertIn("DND属性投点", out)
        self.assertIn("合计:", out)

    def test_handle_invalid_expr_gives_error(self):
        ctx = make_group_message(".r abc")
        plugin = TrpgPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        out = _sent_text(plugin)
        self.assertIn("出错", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
