"""测试活动群聊指令。
运行: python test/test_activity_commands.py
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
        d = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
        p = self._run(f"/活动 创建 匹配 中秋 {d}")
        p.handle()
        self.assertIn("中秋", _sent_text(p))
        act = self.db.activity.get_active_activity(GID)
        self.assertEqual(act["type"], "match")
        self.assertEqual(act["deadline"], d + ":00")

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
        d = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
        self._run(f"/活动 创建 匹配 中秋 {d}").handle()
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

    def test_create_relay_bad_duration_falls_back_to_desc(self):
        """无法解析为时限的尾 token 宽容为描述（描述无引号，无法区分）。"""
        p = self._run("/活动 创建 接龙 t 三天")
        p.handle()
        act = self.db.activity.get_active_activity(GID)
        self.assertIsNotNone(act)
        self.assertEqual(act["description"], "三天")
        self.assertEqual(act["hours_per_user"], 48.0)

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

    def test_create_relay_with_description(self):
        p = self._run("/活动 创建 接龙 端午 围绕粽子自由创作 2天")
        p.handle()
        self.assertIn("围绕粽子自由创作", _sent_text(p))
        act = self.db.activity.get_active_activity(GID)
        self.assertEqual(act["title"], "端午")
        self.assertEqual(act["description"], "围绕粽子自由创作")
        self.assertEqual(act["hours_per_user"], 48.0)

    def test_create_relay_description_multiword(self):
        p = self._run("/活动 创建 接龙 t 这是 一段 描述 48小时")
        p.handle()
        act = self.db.activity.get_active_activity(GID)
        self.assertEqual(act["description"], "这是 一段 描述")
        self.assertEqual(act["hours_per_user"], 48.0)

    def test_create_match_with_description(self):
        d = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
        p = self._run(f"/活动 创建 匹配 中秋 圆桌交换礼物 {d}")
        p.handle()
        self.assertIn("圆桌交换礼物", _sent_text(p))
        act = self.db.activity.get_active_activity(GID)
        self.assertEqual(act["description"], "圆桌交换礼物")
        self.assertEqual(act["deadline"], d + ":00")

    def test_create_relay_no_description_compat(self):
        p = self._run("/活动 创建 接龙 t 2天")
        p.handle()
        act = self.db.activity.get_active_activity(GID)
        self.assertIsNone(act["description"])
        self.assertEqual(act["hours_per_user"], 48.0)

    def test_create_relay_with_deadlines(self):
        """新语法：报名截止 + 活动截止 + 限时 关键字。"""
        sd = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
        dl = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
        p = self._run(f"/活动 创建 接龙 端午 自由创作 报名截止 {sd} 截止 {dl} 限时 2天")
        p.handle()
        self.assertIn("报名截止", _sent_text(p))
        act = self.db.activity.get_active_activity(GID)
        self.assertEqual(act["description"], "自由创作")
        self.assertEqual(act["signup_deadline"], sd + ":00")
        self.assertEqual(act["deadline"], dl + ":00")
        self.assertEqual(act["hours_per_user"], 48.0)

    def test_create_match_with_signup_deadline(self):
        sd = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
        dl = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
        p = self._run(f"/活动 创建 匹配 中秋 圆桌礼物 报名截止 {sd} 截止 {dl}")
        p.handle()
        act = self.db.activity.get_active_activity(GID)
        self.assertEqual(act["description"], "圆桌礼物")
        self.assertEqual(act["signup_deadline"], sd + ":00")
        self.assertEqual(act["deadline"], dl + ":00")

    def test_create_param_duplicate(self):
        p = self._run("/活动 创建 接龙 t 限时 2天 限时 3天")
        p.handle()
        self.assertIn("重复", _sent_text(p))
        self.assertIsNone(self.db.activity.get_active_activity(GID))

    def test_create_param_bad_time(self):
        p = self._run("/活动 创建 接龙 t 报名截止 后天")
        p.handle()
        self.assertIn("时间格式错误", _sent_text(p))
        self.assertIsNone(self.db.activity.get_active_activity(GID))

    def test_create_past_deadline_rejected(self):
        """截止时间早于当前时间 → 创建被拒。"""
        p = self._run("/活动 创建 接龙 t 截止 2000-01-01 00:00")
        p.handle()
        self.assertIn("晚于当前时间", _sent_text(p))
        self.assertIsNone(self.db.activity.get_active_activity(GID))

    def test_create_past_signup_deadline_rejected(self):
        d = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
        p = self._run(f"/活动 创建 匹配 中秋 报名截止 2000-01-01 00:00 截止 {d}")
        p.handle()
        self.assertIn("晚于当前时间", _sent_text(p))
        self.assertIsNone(self.db.activity.get_active_activity(GID))

    def test_start_past_deadline_rejected(self):
        """创建后截止时间已过（模拟时间流逝）→ 开始被拒。"""
        self._run("/活动 创建 接龙 t 截止 2099-01-01 00:00").handle()
        act = self.db.activity.get_active_activity(GID)
        self.db.activity.update_activity(act["id"], deadline="2000-01-01 00:00:00")
        self._run("/活动 加入", user_id=123456).handle()
        p = self._run("/活动 开始", user_id=123456)
        p.handle()
        self.assertIn("无法开始", _sent_text(p))
        self.assertEqual(self.db.activity.get_active_activity(GID)["status"], "open")

    def _group_announce_texts(self, p) -> str:
        """汇总群公告（call_api send_group_msg）文本，警告走此通道。"""
        return "".join(
            seg["data"]["text"]
            for a, c in p.api.api_calls if a == "send_group_msg"
            for seg in c["message"] if seg["type"] == "text"
        )

    def test_start_warns_deadline_conflict(self):
        """接龙截止早于最晚理论完成时间（2人×2天 > 1天）→ 开始群公告警告。"""
        d = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
        self._run(f"/活动 创建 接龙 t 限时 2天 截止 {d}").handle()
        self._run("/活动 加入", user_id=123456).handle()
        self._run("/活动 加入", user_id=234567).handle()
        p = self._run("/活动 开始", user_id=123456)
        p.handle()
        self.assertIn("提醒", self._group_announce_texts(p))

    def test_start_no_warn_without_conflict(self):
        """截止晚于最晚理论完成时间 → 无警告。"""
        d = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
        self._run(f"/活动 创建 接龙 t 限时 2天 截止 {d}").handle()
        self._run("/活动 加入", user_id=123456).handle()
        self._run("/活动 加入", user_id=234567).handle()
        p = self._run("/活动 开始", user_id=123456)
        p.handle()
        self.assertNotIn("提醒", self._group_announce_texts(p))


    def test_status_open_shows_signup_order(self):
        """报名期显示报名序号而非 seq（seq 开始时才生成）。"""
        d = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
        self._run(f"/活动 创建 匹配 中秋 {d}").handle()
        self._run("/活动 加入", user_id=123456).handle()
        self._run("/活动 加入", user_id=234567).handle()
        p = self._run("/活动 状态")
        p.handle()
        text = _sent_text(p)
        self.assertIn("报名中", text)
        self.assertIn("1. 测试用户", text)
        self.assertIn("2. 测试用户", text)
        self.assertNotIn("0.", text)

    def test_status_running_shows_seq(self):
        """开始后显示链/环序。"""
        self._run("/活动 创建 接龙 t").handle()
        self._run("/活动 加入", user_id=123456).handle()
        self._run("/活动 加入", user_id=234567).handle()
        self._run("/活动 开始", user_id=123456).handle()
        p = self._run("/活动 状态")
        p.handle()
        self.assertNotIn("报名中", _sent_text(p))


if __name__ == "__main__":
    unittest.main()
