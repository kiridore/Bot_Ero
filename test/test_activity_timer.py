"""测试活动心跳（超时跳过/截止结束）。
运行: python test/test_activity_timer.py
"""
import os
import sys
import sqlite3
import unittest
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.db._base import init_schema
from core.db.activity import ActivityManager
from core.event import Event
from plugins.activity import ActivityTimerPlugin
from test.helper import MockApiWrapper
import core.context as context

DB_PATH = "/tmp/test_activity_timer.db"
GID = 296470819


class _Db:
    def __init__(self, conn):
        self.activity = ActivityManager(conn)


def _setup(db, type_):
    aid = db.activity.create_activity(
        GID, type_, "t", None, "1",
        hours_per_user=24.0 if type_ == "relay" else None,
        deadline=None if type_ == "relay" else "2026-09-15 20:00:00",
    )
    for uid, nick in (("100", "A"), ("200", "B")):
        db.activity.add_member(aid, uid, nick)
    db.activity.update_activity(aid, status="running")
    if type_ == "relay":
        db.activity.set_ring(aid, [("100", "200", 1), ("200", None, 2)])
    else:
        db.activity.set_ring(aid, [("100", "200", 1), ("200", "100", 2)])
    return aid


class TestTimer(unittest.TestCase):
    def setUp(self):
        for p in (DB_PATH, "/tmp/test_activity_archive_timer"):
            if os.path.exists(p):
                if os.path.isdir(p):
                    import shutil; shutil.rmtree(p)
                else:
                    os.remove(p)
        self.conn = sqlite3.connect(DB_PATH)
        init_schema(self.conn, self.conn.cursor())
        self.db = _Db(self.conn)
        context.python_data_path = "/tmp/test_activity_archive_timer"
        ActivityTimerPlugin._last_scan = {}

    def tearDown(self):
        self.conn.close()

    def _plugin(self):
        raw = {"post_type": "meta", "meta_event_type": "heartbeat",
               "time": 0, "message_type": "meta_event"}
        p = ActivityTimerPlugin.__new__(ActivityTimerPlugin)
        p.bot_event = Event(raw)
        p.api = MockApiWrapper(raw)
        p.dbmanager = self.db
        return p

    def test_relay_timeout_skips(self):
        aid = _setup(self.db, "relay")
        old = (datetime.now() - timedelta(hours=30)).strftime("%Y-%m-%d %H:%M:%S")
        self.db.activity.update_member(aid, "100", received_at=old)
        self._plugin().handle()
        self.assertEqual(self.db.activity.get_member(aid, "100")["status"], "skipped")
        b = self.db.activity.get_member(aid, "200")
        self.assertIsNotNone(b["received_at"])          # 顺延并开始计时

    def test_relay_no_timeout(self):
        aid = _setup(self.db, "relay")
        future = (datetime.now() + timedelta(seconds=2)).strftime("%Y-%m-%d %H:%M:%S")
        self.db.activity.update_member(aid, "100", received_at=future)
        self._plugin().handle()
        self.assertEqual(self.db.activity.get_member(aid, "100")["status"], "pending")

    def test_match_deadline_finishes(self):
        aid = _setup(self.db, "match")
        self.db.activity.update_activity(aid, deadline="2000-01-01 00:00:00")
        self._plugin().handle()
        act = self.db.activity.get_activity(aid)
        self.assertEqual(act["status"], "finished")
        self.assertEqual(self.db.activity.get_member(aid, "100")["status"], "missed")
        self.assertEqual(self.db.activity.get_member(aid, "200")["status"], "missed")


if __name__ == "__main__":
    unittest.main()
