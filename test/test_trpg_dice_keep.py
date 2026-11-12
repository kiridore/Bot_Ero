"""骰子取高/取低（k/kh/kl）与严格解析（未知字符不再静默截断）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from plugins.trpg_dice.dice import parse
from plugins.trpg_dice import TrpgPlugin
from test.helper import MockApiWrapper, make_group_message


def _sent(plugin) -> str:
    return plugin.api.sent_messages[-1][1][0]["data"]["text"]


def _roll(msg: str) -> str:
    ctx = make_group_message(msg)
    plugin = TrpgPlugin(ctx)
    plugin.api = MockApiWrapper(ctx)
    plugin.handle()
    return _sent(plugin)


class TestKeepHighest(unittest.TestCase):
    def test_k_suffix_keeps_three(self):
        with patch("plugins.trpg_dice.dice.random.randint", side_effect=[3, 6, 2, 5]):
            value, detail = parse("4d6k3")
        self.assertEqual(value, 14)          # 6 + 5 + 3
        self.assertIn("弃 2", detail)

    def test_kh_suffix_same_as_k(self):
        with patch("plugins.trpg_dice.dice.random.randint", side_effect=[3, 6, 2, 5]):
            self.assertEqual(parse("4d6kh3")[0], 14)

    def test_keep_lowest(self):
        with patch("plugins.trpg_dice.dice.random.randint", side_effect=[3, 6, 2, 5]):
            value, detail = parse("4d6kl1")
        self.assertEqual(value, 2)
        self.assertIn("弃 3 5 6", detail)

    def test_keep_without_number_defaults_to_one(self):
        with patch("plugins.trpg_dice.dice.random.randint", side_effect=[4, 1, 6]):
            self.assertEqual(parse("3d6k")[0], 6)

    def test_keep_larger_than_count_rejected(self):
        with patch("plugins.trpg_dice.dice.random.randint", side_effect=[1, 2]):
            with self.assertRaises(ValueError):
                parse("2d6k5")

    def test_keep_inside_expression(self):
        with patch("plugins.trpg_dice.dice.random.randint", side_effect=[3, 6, 2, 5]):
            self.assertEqual(parse("4d6k3+2")[0], 16)


class TestStrictParsing(unittest.TestCase):
    def test_unknown_tail_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            parse("2d6+abc")
        self.assertIn("abc", str(ctx.exception))

    def test_command_reports_unparsable(self):
        out = _roll(".r 4d6k3x")
        self.assertIn("无法解析", out)

    def test_reason_after_space_still_works(self):
        with patch("plugins.trpg_dice.dice.random.randint", return_value=7):
            out = _roll(".r 1d20 偷袭")
        self.assertIn("偷袭", out)
        self.assertIn("1d20", out)

    def test_plain_expression_unaffected(self):
        with patch("plugins.trpg_dice.dice.random.randint", side_effect=[6, 1]):
            self.assertEqual(parse("2d6")[0], 7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
