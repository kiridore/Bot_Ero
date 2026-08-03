"""测试活动群聊指令。
运行: python test/test_activity_commands.py
"""
import os
import sys
import sqlite3
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import core.context as context
from core.event import Event
from core.db._base import init_schema
from core.db.activity import ActivityManager
from plugins.activity import ActivityPlugin
from test.helper import MockApiWrapper, make_group_message

DB_PATH = "/tmp/test_activity_cmd.db"
GID = 296470819


class _Db:
    """测试用：仅挂 activity 管理器，跳过真实 DbManager 的全局库。"""
    def __init__(self, conn):
        self.activity = ActivityManager(conn)


def _sent_text(plugin):
    assert plugin.api.sent_messages, "无消息发送"
    return plugin.api.sent_messages[-1][1][0]["data"]["text"]


class TestCommands(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        self.conn = sqlite3.connect(DB_PATH)
        init_schema(self.conn, self.conn.cursor())
        self.db = _Db(self.conn)
        self.old_python_data_path = context.python_data_path
        context.python_data_path = "/tmp/test_activity_archive_cmd"

    def tearDown(self):
        self.conn.close()

    def _run(self, text, user_id=123456):
        raw = make_group_message(text, user_id=user_id, group_id=GID)
        plugin = ActivityPlugin.__new__(ActivityPlugin)
        plugin.bot_event = Event(raw)
        plugin.api = MockApiWrapper(raw)
        plugin.dbmanager = self.db
        return plugin

    def test_create_relay(self):
        p = self._run("/活动 创建 接龙 端午接龙")
        p.handle()
        self.assertIn("端午接龙", _sent_text(p))
        act = self.db.activity.get_active_activity(GID)
        self.assertIsNotNone(act)
        self.assertEqual(act["type"], "relay")
        self.assertEqual(act["hours_per_user"], 48.0)

    def test_create_match_deadline(self):
        p = self._run("/活动 创建 匹配 中秋 2026-09-15 20:00")
        p.handle()
        self.assertIn("中秋", _sent_text(p))
        act = self.db.activity.get_active_activity(GID)
        self.assertEqual(act["type"], "match")
        self.assertEqual(act["deadline"], "2026-09-15 20:00:00")

    def test_join_and_start_relay(self):
        self._run("/活动 创建 接龙 端午接龙").handle()
        for uid in (123456, 234567):
            p = self._run("/活动 加入", user_id=uid)
            p.handle()
            self.assertIn("已加入", _sent_text(p))
        p = self._run("/活动 开始", user_id=123456)
        p.handle()
        self.assertIn("开始", _sent_text(p))
        act = self.db.activity.get_active_activity(GID)
        self.assertEqual(act["status"], "running")
        members = self.db.activity.get_members(act["id"])
        self.assertEqual([m["seq"] for m in members], [1, 2])
        self.assertEqual(members[0]["next_user_id"], members[1]["user_id"])
        self.assertIsNone(members[1]["next_user_id"])
        self.assertIsNotNone(members[0]["received_at"])  # 第一棒已开始计时

    def test_start_only_creator(self):
        self._run("/活动 创建 接龙 t").handle()
        self._run("/活动 加入", user_id=123456).handle()
        p = self._run("/活动 开始", user_id=999999)
        p.handle()
        self.assertIn("创建人", _sent_text(p))

    def test_match_needs_two(self):
        self._run("/活动 创建 匹配 中秋 2026-09-15 20:00").handle()
        self._run("/活动 加入", user_id=123456).handle()
        p = self._run("/活动 开始", user_id=123456)
        p.handle()
        self.assertIn("至少", _sent_text(p))

    def test_leave_open_transfers_creator(self):
        self._run("/活动 创建 接龙 t").handle()
        self._run("/活动 加入", user_id=123456).handle()
        self._run("/活动 加入", user_id=234567).handle()
        p = self._run("/活动 退出", user_id=123456)
        p.handle()
        act = self.db.activity.get_active_activity(GID)
        self.assertEqual(act["created_by"], "234567")
        self.assertIn("转移", _sent_text(p))

    def test_create_relay_days(self):
        """时限支持天单位：2天 = 48 小时。"""
        p = self._run("/活动 创建 接龙 中秋接龙 2天")
        p.handle()
        self.assertIn("2 天", _sent_text(p))
        act = self.db.activity.get_active_activity(GID)
        self.assertEqual(act["hours_per_user"], 48.0)

    def test_create_relay_bad_duration(self):
        p = self._run("/活动 创建 接龙 t 三天")
        p.handle()
        self.assertIn("时限", _sent_text(p))
        self.assertIsNone(self.db.activity.get_active_activity(GID))

    def test_parse_duration(self):
        from plugins.activity import _parse_duration
        self.assertEqual(_parse_duration("48"), 48.0)
        self.assertEqual(_parse_duration("48小时"), 48.0)
        self.assertEqual(_parse_duration("2天"), 48.0)
        self.assertEqual(_parse_duration("1.5天"), 36.0)
        self.assertEqual(_parse_duration("2d"), 48.0)
        self.assertEqual(_parse_duration(" 3 天 "), 72.0)
        self.assertIsNone(_parse_duration("abc"))
        self.assertIsNone(_parse_duration("0小时"))
        self.assertIsNone(_parse_duration("-2天"))


if __name__ == "__main__":
    unittest.main()
