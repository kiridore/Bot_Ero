"""仙人彩纯函数测试：注单按人聚合、逐位判定、奖池分配。

运行: pytest test/test_immortal_lottery.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from plugins.immortal_lottery.helpers import (
    _allocate_tier_pool,
    _bets_by_user,
    _count_a,
)


class TestBetsByUser(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(_bets_by_user([]), [])

    def test_aggregates_and_keeps_order(self):
        bets = [(1, 100, "1111"), (2, 200, "2222"), (3, 100, "3333"), (4, 300, "0000"), (5, 200, "1212")]
        self.assertEqual(_bets_by_user(bets), [
            (100, ["1111", "3333"]),
            (200, ["2222", "1212"]),
            (300, ["0000"]),
        ])


class TestCountA(unittest.TestCase):
    def test_positional_match(self):
        self.assertEqual(_count_a("1234", "1234"), 4)
        self.assertEqual(_count_a("1234", "1235"), 3)
        self.assertEqual(_count_a("1234", "1265"), 2)
        self.assertEqual(_count_a("1234", "4321"), 0)  # 逐位相同，非乱序


class TestAllocateTierPool(unittest.TestCase):
    def test_even_split(self):
        detail, payouts, rem = _allocate_tier_pool(10, [(1, "1111"), (2, "2222")], "一等奖(4A)")
        self.assertEqual(detail, [(1, 5, "一等奖(4A) 1111"), (2, 5, "一等奖(4A) 2222")])
        self.assertEqual(payouts, [(1, 5), (2, 5)])
        self.assertEqual(rem, 0)

    def test_remainder_carries(self):
        _detail, payouts, rem = _allocate_tier_pool(7, [(1, "1111"), (2, "2222"), (3, "3333")], "三等奖(2A)")
        self.assertEqual(payouts, [(1, 2), (2, 2), (3, 2)])
        self.assertEqual(rem, 1)

    def test_insufficient_pool_pays_in_order(self):
        _detail, payouts, rem = _allocate_tier_pool(1, [(1, "1111"), (2, "2222")], "一等奖(4A)")
        self.assertEqual(payouts, [(1, 1)])
        self.assertEqual(rem, 0)
