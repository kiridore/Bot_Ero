"""测试活动纯逻辑（环/链/超时）。
运行: pytest test/test_activity_logic.py
"""
import sys
import random
import unittest
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from plugins.activity.logic import (
    build_ring, relay_assignments, current_turn, next_pending,
    last_done, is_timeout, relay_done,
)


def _member(uid, seq, status="pending", received_at=None):
    return {"user_id": uid, "seq": seq, "status": status, "received_at": received_at}


class TestRing(unittest.TestCase):
    def test_single_cycle_no_self(self):
        users = ["1", "2", "3", "4", "5"]
        ring = build_ring(users, rng=random.Random(42))
        self.assertEqual(len(ring), 5)
        nxt = {u: n for u, n in ring}
        self.assertEqual(set(nxt), set(users))          # 人人有下家
        for u, n in ring:
            self.assertNotEqual(u, n)                   # 无自匹配
        # 单环闭合：从任一点沿 next 走 5 步回到原点
        cur = ring[0][0]
        for _ in range(5):
            cur = nxt[cur]
        self.assertEqual(cur, ring[0][0])

    def test_ring_needs_two(self):
        with self.assertRaises(ValueError):
            build_ring(["1"])


class TestRelayChain(unittest.TestCase):
    def test_assignments(self):
        users = ["1", "2", "3"]
        assigns = relay_assignments(users, rng=random.Random(1))
        self.assertEqual([a[2] for a in assigns], [1, 2, 3])   # seq 连续
        self.assertEqual({a[0] for a in assigns}, set(users))
        for a, b in zip(assigns, assigns[1:]):
            self.assertEqual(a[1], b[0])                        # 链连续性
        self.assertIsNone(assigns[-1][1])                       # 末位无下家


class TestChainNav(unittest.TestCase):
    def setUp(self):
        self.members = [_member("1", 1), _member("2", 2), _member("3", 3)]

    def test_current_turn(self):
        self.assertEqual(current_turn(self.members)["user_id"], "1")
        self.members[0]["status"] = "done"
        self.assertEqual(current_turn(self.members)["user_id"], "2")
        for m in self.members:
            m["status"] = "skipped"
        self.assertIsNone(current_turn(self.members))

    def test_next_pending_skips_left(self):
        self.members[1]["status"] = "left"
        self.assertEqual(next_pending(self.members, after_seq=1)["user_id"], "3")
        self.assertIsNone(next_pending(self.members, after_seq=3))

    def test_last_done(self):
        self.members[0]["status"] = "done"
        self.members[1]["status"] = "done"
        got = last_done(self.members, before_seq=3)
        self.assertEqual(got["user_id"], "2")
        # 边界：before_seq 不包含自身（seq==2 的 done 不计入 before_seq=2）
        self.assertIsNone(last_done(
            [_member("1", 1), _member("2", 2, status="done")], before_seq=2))

    def test_relay_done(self):
        self.assertFalse(relay_done(self.members))
        for m in self.members:
            m["status"] = "done"
        self.assertTrue(relay_done(self.members))


class TestTimeout(unittest.TestCase):
    def test_timeout(self):
        now = datetime(2026, 9, 1, 12, 0, 0)
        self.assertTrue(is_timeout("2026-09-01 00:00:00", now, 10.0))
        self.assertFalse(is_timeout("2026-09-01 09:00:00", now, 10.0))
        self.assertFalse(is_timeout(None, now, 10.0))       # 尚未开始计时

    def test_boundary(self):
        now = datetime(2026, 9, 1, 10, 0, 1)
        self.assertTrue(is_timeout("2026-09-01 00:00:00", now, 10.0))
        self.assertFalse(is_timeout("2026-09-01 00:00:01", now, 10.0))


if __name__ == "__main__":
    unittest.main()
