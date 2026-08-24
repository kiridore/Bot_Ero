"""仙人彩纯函数与总奖池 DB 层测试：比例派发（等比均分、奖级单调不倒挂、池浅保底）、
单一滚存 carry_total 读写、开奖事务、旧三列滚存迁移。

运行: pytest test/test_immortal_lottery.py
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.db._base import init_schema
from core.database_manager import DbManager
from plugins.immortal_lottery.helpers import (
    _TIER_RATE_PCT,
    _bets_by_user,
    _count_a,
    _payout_tier,
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


class TestPayoutTier(unittest.TestCase):
    def test_single_bet_takes_rate_of_pool(self):
        detail, payouts, take = _payout_tier(100, [(1, "1111")], 40, "一等奖(4A)")
        self.assertEqual(take, 40)
        self.assertEqual(detail, [(1, 40, "一等奖(4A) 1111")])
        self.assertEqual(payouts, [(1, 40)])

    def test_two_bets_geometric_split_evenly(self):
        # n=2 合计拿走 1-(1-r)^2 = 64%，均分各 32
        _detail, payouts, take = _payout_tier(100, [(1, "1111"), (2, "2222")], 40, "一等奖(4A)")
        self.assertEqual(take, 64)
        self.assertEqual(payouts, [(1, 32), (2, 32)])

    def test_higher_tier_always_outpays_lower(self):
        # 回归：单一总池逐级派发，任何注数组合下高奖级单注 > 低奖级单注（不倒挂）
        pool = 1000
        _d4, p4, take4 = _payout_tier(pool, [(1, "a"), (2, "b")], _TIER_RATE_PCT[4], "一等奖(4A)")
        pool -= take4
        _d3, p3, take3 = _payout_tier(pool, [(3, "c")], _TIER_RATE_PCT[3], "二等奖(3A)")
        pool -= take3
        _d2, p2, take2 = _payout_tier(pool, [(4, "d"), (5, "e"), (6, "f")], _TIER_RATE_PCT[2], "三等奖(2A)")
        self.assertTrue(min(a for _u, a in p4) > max(a for _u, a in p3))
        self.assertTrue(min(a for _u, a in p3) > max(a for _u, a in p2))

    def test_shallow_pool_pays_one_each_in_order(self):
        # 合计不足 n 分：按下注先后各 1 分至耗尽
        detail, payouts, take = _payout_tier(2, [(1, "1111"), (2, "2222"), (3, "3333")], 40, "一等奖(4A)")
        self.assertEqual(take, 1)
        self.assertEqual(payouts, [(1, 1)])
        self.assertEqual([d[1] for d in detail], [1, 0, 0])

    def test_zero_pool_or_no_winners(self):
        self.assertEqual(_payout_tier(0, [(1, "1111")], 40, "一等奖(4A)"), ([], [], 0))
        self.assertEqual(_payout_tier(100, [], 40, "一等奖(4A)"), ([], [], 0))


class TestImmortalManager(unittest.TestCase):
    def setUp(self):
        self.db = DbManager()
        self.gid = 296470819
        self.db.cur.execute("DELETE FROM immortal_lottery_results")
        self.db.cur.execute("DELETE FROM immortal_lottery_bets")
        self.db.cur.execute("DELETE FROM immortal_lottery_carry")
        self.db.conn.commit()

    def tearDown(self):
        self.db.cur.execute("DELETE FROM immortal_lottery_results")
        self.db.cur.execute("DELETE FROM immortal_lottery_bets")
        self.db.cur.execute("DELETE FROM immortal_lottery_carry")
        self.db.conn.commit()
        self.db.conn.close()

    def test_carry_single_pool_roundtrip(self):
        self.assertEqual(self.db.immortal.carry(self.gid), 0)
        self.db.immortal.set_carry(self.gid, 123)
        self.assertEqual(self.db.immortal.carry(self.gid), 123)

    def test_finalize_draw_atomic(self):
        ok = self.db.immortal.finalize_draw(
            self.gid, "2026-08-17", "1234", 2, "2026-08-23 20:00:00", 7, [(501, 5)],
        )
        self.assertTrue(ok)
        self.assertTrue(self.db.immortal.has_result(self.gid, "2026-08-17"))
        self.assertEqual(self.db.immortal.carry(self.gid), 7)
        self.db.cur.execute("SELECT points FROM user_assets WHERE user_id = '501'")
        self.assertEqual(self.db.cur.fetchone()[0], 5)
        # 同期重复开奖被拒绝
        self.assertFalse(self.db.immortal.finalize_draw(
            self.gid, "2026-08-17", "5678", 2, "2026-08-23 20:01:00", 0, [],
        ))


class TestCarryTotalMigration(unittest.TestCase):
    def test_old_three_columns_merge_into_total(self):
        # 构造 1.22 及之前的旧表结构（无 carry_total），init_schema 应并入单一总池并清零旧列
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "old.db"
            conn = sqlite3.connect(str(path))
            conn.execute(
                """CREATE TABLE immortal_lottery_carry (
                    group_id INTEGER NOT NULL PRIMARY KEY,
                    carry_4a INTEGER NOT NULL DEFAULT 0,
                    carry_3a INTEGER NOT NULL DEFAULT 0,
                    carry_2a INTEGER NOT NULL DEFAULT 0
                )"""
            )
            conn.execute(
                "INSERT INTO immortal_lottery_carry (group_id, carry_4a, carry_3a, carry_2a)"
                " VALUES (296470819, 10, 6, 3)"
            )
            conn.commit()
            init_schema(conn, conn.cursor())
            conn.commit()
            cur = conn.execute(
                "SELECT carry_total, carry_4a, carry_3a, carry_2a FROM immortal_lottery_carry"
                " WHERE group_id = 296470819"
            )
            self.assertEqual(cur.fetchone(), (19, 0, 0, 0))
            # 幂等：再跑一次不重复累加
            init_schema(conn, conn.cursor())
            conn.commit()
            cur = conn.execute(
                "SELECT carry_total FROM immortal_lottery_carry WHERE group_id = 296470819"
            )
            self.assertEqual(cur.fetchone()[0], 19)
            conn.close()
