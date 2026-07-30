"""测试 DicePlugin 示例。

运行: python test/test_dice.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from plugins.dice import DicePlugin
from test.helper import MockApiWrapper, make_group_message


def _sent_text(plugin) -> str:
    """取插件发出的唯一一条消息的纯文本。"""
    assert len(plugin.api.sent_messages) == 1, "预期只发一条消息"
    return plugin.api.sent_messages[0][1][0]["data"]["text"]


class TestDicePlugin(unittest.TestCase):
    def test_match_accepts_valid_roll(self):
        ctx = make_group_message(".r2d6")
        self.assertTrue(DicePlugin(ctx).match("message"))

    def test_match_rejects_non_roll(self):
        ctx = make_group_message("hello")
        self.assertFalse(DicePlugin(ctx).match("message"))

    @patch("plugins.dice.random.randint", side_effect=[3, 5])
    def test_handle_exact_output(self, _):
        ctx = make_group_message(".r2d6")
        plugin = DicePlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        self.assertEqual(_sent_text(plugin), ".r2d6\n结果：3 + 5\n总和：8")

    @patch("plugins.dice.random.randint", side_effect=[1])
    def test_handle_single_die(self, _):
        ctx = make_group_message(".r1d20")
        plugin = DicePlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        self.assertEqual(_sent_text(plugin), ".r1d20\n结果：1\n总和：1")

    def test_handle_values_in_range_and_sum_matches(self):
        for trial in range(200):
            ctx = make_group_message(".r3d6")
            plugin = DicePlugin(ctx)
            plugin.api = MockApiWrapper(ctx)
            plugin.handle()
            body = _sent_text(plugin)
            self.assertTrue(body.startswith(".r3d6\n结果："), body)
            numbers = [int(x) for x in body.split("\n")[1].split("结果：")[1].split(" + ")]
            self.assertEqual(len(numbers), 3)
            self.assertTrue(all(1 <= n <= 6 for n in numbers), numbers)
            total_line = body.split("\n")[2]
            self.assertEqual(total_line, "总和：{}".format(sum(numbers)))

    def test_handle_rejects_excessive_dice(self):
        ctx = make_group_message(".r200d6")
        plugin = DicePlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        self.assertEqual(_sent_text(plugin), "为了防止刷屏，限制为最多100个骰子、1000面")

    def test_handle_rejects_nonpositive(self):
        ctx = make_group_message(".r0d6")
        plugin = DicePlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        self.assertEqual(_sent_text(plugin), "骰子数量和面数都必须大于0")

    @patch("plugins.dice.random.randint", side_effect=[6, 6, 6, 6, 6])
    def test_handle_case_insensitive_match_but_lowercase_echo(self, _):
        # ponytail: 固化现状——输入大小写不敏感匹配，但回显强制小写；若改为原样回显需同步更新此断言
        ctx = make_group_message(".R5D6")
        plugin = DicePlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        self.assertTrue(plugin.match("message"))
        plugin.handle()
        self.assertEqual(_sent_text(plugin), ".r5d6\n结果：6 + 6 + 6 + 6 + 6\n总和：30")


if __name__ == "__main__":
    unittest.main(verbosity=2)