"""测试活动数据访问层。
运行: pytest test/test_activity_db.py
"""
import os
import sys
import sqlite3
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.db.activity import ActivityManager

DB_PATH = "/tmp/test_activity.db"


class TestActivityDb(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        self.conn = sqlite3.connect(DB_PATH)
        from core.db._base import init_schema
        init_schema(self.conn, self.conn.cursor())
        self.m = ActivityManager(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_create_and_get(self):
        aid = self.m.create_activity(296470819, "relay", "端午接龙", "粽子", "1", hours_per_user=48.0)
        act = self.m.get_activity(aid)
        self.assertEqual(act["type"], "relay")
        self.assertEqual(act["status"], "open")

    def test_active_activity(self):
        aid = self.m.create_activity(1, "match", "中秋", None, "1", deadline="2026-09-15 20:00:00")
        got = self.m.get_active_activity(1)
        self.assertEqual(got["id"], aid)
        self.assertIsNone(self.m.get_active_activity(2))
        self.m.update_activity(aid, status="finished", finished_at="2026-09-01 00:00:00")
        self.assertIsNone(self.m.get_active_activity(1))

    def test_member_flow(self):
        aid = self.m.create_activity(1, "relay", "t", None, "1", hours_per_user=24.0)
        self.assertTrue(self.m.add_member(aid, "100", "A"))
        self.assertFalse(self.m.add_member(aid, "100", "A"))  # 重复加入
        self.m.add_member(aid, "200", "B")
        self.assertEqual(self.m.count_members(aid), 2)
        self.m.remove_member(aid, "200")
        self.assertEqual(self.m.count_members(aid), 1)

    def test_ring_and_updates(self):
        aid = self.m.create_activity(1, "match", "t", None, "1", deadline="2026-09-15 20:00:00")
        for uid, nick in (("100", "A"), ("200", "B"), ("300", "C")):
            self.m.add_member(aid, uid, nick)
        self.m.set_ring(aid, [("100", "200", 1), ("200", "300", 2), ("300", "100", 3)])
        members = self.m.get_members(aid)
        by_uid = {m["user_id"]: m for m in members}
        self.assertEqual(by_uid["100"]["next_user_id"], "200")
        self.assertEqual(by_uid["100"]["seq"], 1)
        self.m.update_member(aid, "100", status="done", content="作品", submitted_at="2026-09-01 00:00:00")
        got = self.m.get_member(aid, "100")
        self.assertEqual(got["status"], "done")
        self.assertEqual(got["content"], "作品")

    def test_user_activities(self):
        aid = self.m.create_activity(1, "relay", "t", None, "1", hours_per_user=24.0)
        self.m.add_member(aid, "100", "A")
        self.m.update_activity(aid, status="running")
        acts = self.m.get_running_activities_for_user("100")
        self.assertEqual(len(acts), 1)
        self.assertEqual(acts[0]["id"], aid)
        self.assertEqual(self.m.get_running_activity_for_user_and_id("100", aid)["id"], aid)


if __name__ == "__main__":
    unittest.main()
