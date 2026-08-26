"""补卡插件权限与日期校验回归。
运行: pytest test/test_remedy_checkin.py
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

import test.helper  # noqa: F401

from core.event import Event
from core.db._base import init_schema
from core.db.checkin import CheckinManager
from core.db.points import PointsManager
from plugins.remedy_checkin import RemedyCheckinPlugin
from test.helper import MockApiWrapper

DB_PATH = "/tmp/test_remedy_checkin.db"

PAST_MONDAY = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")   # 上上周内某天
FUTURE_DATE = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")   # 两周后


def _raw(text_body, user_id=123456, role="member"):
    return {
        "post_type": "message", "message_type": "group", "user_id": user_id,
        "group_id": 296470819,
        "message": [{"type": "text", "data": {"text": text_body}}],
        "sender": {"user_id": user_id, "nickname": "测试用户", "role": role},
        "time": 0, "message_id": -1,
    }


class _Db:
    def __init__(self, conn):
        self.checkin = CheckinManager(conn)
        self.points = PointsManager(conn)


def _last_text(plugin):
    assert plugin.api.sent_messages, "无消息发送"
    return "".join(seg["data"].get("text", "") for seg in plugin.api.sent_messages[-1][1]
                   if seg["type"] == "text")


class TestRemedyGuard(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        self.conn = sqlite3.connect(DB_PATH)
        init_schema(self.conn, self.conn.cursor())
        self.db = _Db(self.conn)

    def tearDown(self):
        self.conn.close()

    def _run(self, text_body, user_id=123456, role="member"):
        plugin = RemedyCheckinPlugin.__new__(RemedyCheckinPlugin)
        plugin.bot_event = Event(_raw(text_body, user_id, role))
        plugin.api = MockApiWrapper(_raw(text_body, user_id, role))
        plugin.dbmanager = self.db
        plugin.match("message")
        plugin.handle()
        return plugin

    def test_super_remedy_denied_for_member(self):
        plugin = self._run(f"/超级补卡 {PAST_MONDAY}")
        self.assertIn("管理员", _last_text(plugin))
        self.assertEqual(self.db.checkin.search_user_range(123456, "2000-01-01 00:00:00", "2100-01-01 00:00:00"), [])

    def test_remedy_for_other_denied_for_member(self):
        self.db.points.set("123456", 10)
        plugin = self._run(f"/补卡 {PAST_MONDAY} 999999")
        self.assertIn("管理员", _last_text(plugin))
        self.assertEqual(self.db.checkin.remedy_used(datetime.now().year, "999999"), 0)

    def test_future_week_rejected(self):
        self.db.points.set("123456", 10)
        plugin = self._run(f"/补卡 {FUTURE_DATE}")
        self.assertIn("还没过完", _last_text(plugin))
        rows = self.db.checkin.search_user_range(123456, "2000-01-01 00:00:00", "2100-01-01 00:00:00")
        self.assertEqual(rows, [])

    def test_future_single_day_rejected(self):
        self.db.points.set("123456", 10)
        plugin = self._run(f"/单日补卡 {FUTURE_DATE}")
        self.assertIn("还没过完", _last_text(plugin))
        rows = self.db.checkin.search_user_range(123456, "2000-01-01 00:00:00", "2100-01-01 00:00:00")
        self.assertEqual(rows, [])

    def test_admin_super_remedy_for_other_succeeds_free(self):
        self.db.points.set("777777", 0)  # 目标用户 0 分也能被管理员免费补
        plugin = self._run(f"/超级补卡 {PAST_MONDAY} 777777", user_id=42, role="owner")
        self.assertIn("补上了喵", _last_text(plugin))
        self.assertEqual(self.db.points.get("777777"), 0)  # 免扣分
        self.assertEqual(self.db.checkin.remedy_used(datetime.now().year, "777777"), 0)  # 免额度

    def test_member_past_week_succeeds_paid(self):
        self.db.points.set("123456", 10)
        plugin = self._run(f"/补卡 {PAST_MONDAY}")
        self.assertIn("补上了喵", _last_text(plugin))
        self.assertEqual(self.db.points.get("123456"), 6)  # 10 - 4
        self.assertEqual(self.db.checkin.remedy_used(datetime.now().year, "123456"), 1)


if __name__ == "__main__":
    unittest.main()
