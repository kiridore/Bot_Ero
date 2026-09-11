"""测试活动群聊指令。
运行: pytest test/test_activity_commands.py
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
from core.tiptap import plain_to_tiptap
from core.db._base import init_schema
from core.db.activity import ActivityManager
import plugins.activity as activity_mod
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
        # 隔离时间线事件网络调用（best-effort 也会打 127.0.0.1，测试统一拦截记录）
        self.timeline_events = []
        self._orig_emit = activity_mod.emit_event
        activity_mod.emit_event = lambda **kw: self.timeline_events.append(kw)

    def tearDown(self):
        context.python_data_path = self.old_python_data_path
        activity_mod.emit_event = self._orig_emit
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
        self.assertEqual(act["description"], plain_to_tiptap("三天"))
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
        self.assertEqual(act["description"], plain_to_tiptap("围绕粽子自由创作"))
        self.assertEqual(act["hours_per_user"], 48.0)

    def test_create_relay_description_multiword(self):
        p = self._run("/活动 创建 接龙 t 这是 一段 描述 48小时")
        p.handle()
        act = self.db.activity.get_active_activity(GID)
        self.assertEqual(act["description"], plain_to_tiptap("这是 一段 描述"))
        self.assertEqual(act["hours_per_user"], 48.0)

    def test_create_match_with_description(self):
        d = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
        p = self._run(f"/活动 创建 匹配 中秋 圆桌交换礼物 {d}")
        p.handle()
        self.assertIn("圆桌交换礼物", _sent_text(p))
        act = self.db.activity.get_active_activity(GID)
        self.assertEqual(act["description"], plain_to_tiptap("圆桌交换礼物"))
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
        self.assertEqual(act["description"], plain_to_tiptap("自由创作"))
        self.assertEqual(act["signup_deadline"], sd + ":00")
        self.assertEqual(act["deadline"], dl + ":00")
        self.assertEqual(act["hours_per_user"], 48.0)

    def test_create_match_with_signup_deadline(self):
        sd = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
        dl = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
        p = self._run(f"/活动 创建 匹配 中秋 圆桌礼物 报名截止 {sd} 截止 {dl}")
        p.handle()
        act = self.db.activity.get_active_activity(GID)
        self.assertEqual(act["description"], plain_to_tiptap("圆桌礼物"))
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

    def test_timeline_lifecycle_events(self):
        """创建→开始→结束全生命周期各发一条时间线事件（actor=小埃同学）。"""
        self._run("/活动 创建 接龙 生命周期").handle()
        self._run("/活动 加入", user_id=123456).handle()
        self._run("/活动 开始", user_id=123456).handle()
        self._run("/活动 结束", user_id=123456).handle()
        acts = self.timeline_events
        self.assertEqual(len(acts), 3)
        self.assertEqual([a["dedup_key"].rsplit(":", 1)[-1] for a in acts], ["signup", "start", "finish"])
        for a in acts:
            self.assertEqual(a["source"], "activity")
            self.assertEqual(a["actor_id"], activity_mod.BOT_QQ)
            self.assertEqual(a["actor_qq"], activity_mod.BOT_QQ)
            self.assertTrue(a["title"].startswith("「生命周期」"))
            self.assertEqual(a["target_url"], "/activities/1")
        self.assertIn("开始报名", acts[0]["title"])
        self.assertIn("正式开始", acts[1]["title"])
        self.assertIn("已结束归档", acts[2]["title"])

    # ── 单群多活动并行 ──

    def test_multi_create_join_start_by_id(self):
        """同群两个活动并行：创建不再互斥，加入/开始/状态/结束均可指定编号。"""
        d = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
        self._run("/活动 创建 接龙 甲活动").handle()
        p = self._run(f"/活动 创建 征集 乙活动 {d}")
        p.handle()
        self.assertIn("已创建", _sent_text(p))  # 不再报「已有进行中的活动」
        acts = self.db.activity.get_active_activities_for_group(GID)
        self.assertEqual(len(acts), 2)
        aid_a, aid_b = acts[0]["id"], acts[1]["id"]

        p = self._run("/活动 加入", user_id=999999)
        p.handle()
        self.assertIn("多个活动", _sent_text(p))  # 两个 open 候选 → 要求指定编号

        p = self._run(f"/活动 加入 {aid_b}", user_id=234567)
        p.handle()
        self.assertIn("已加入", _sent_text(p))
        self.assertIsNone(self.db.activity.get_member(aid_a, "234567"))
        self.assertIsNotNone(self.db.activity.get_member(aid_b, "234567"))

        p = self._run(f"/活动 开始 {aid_b}", user_id=123456)
        p.handle()
        self.assertEqual(self.db.activity.get_activity(aid_b)["status"], "running")
        self.assertEqual(self.db.activity.get_activity(aid_a)["status"], "open")

        p = self._run("/活动 状态")
        p.handle()
        t = _sent_text(p)
        self.assertIn(f"#{aid_a}", t)
        self.assertIn(f"#{aid_b}", t)
        self.assertIn("进行中", t)

        p = self._run(f"/活动 结束 {aid_a}", user_id=123456)
        p.handle()
        self.assertEqual(self.db.activity.get_activity(aid_a)["status"], "cancelled")
        self.assertEqual(self.db.activity.get_activity(aid_b)["status"], "running")

    def test_multi_leave_by_id(self):
        d = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
        self._run("/活动 创建 接龙 甲活动").handle()
        self._run(f"/活动 创建 征集 乙活动 {d}").handle()
        acts = self.db.activity.get_active_activities_for_group(GID)
        aid_a, aid_b = acts[0]["id"], acts[1]["id"]
        self._run(f"/活动 加入 {aid_a}", user_id=234567).handle()
        self._run(f"/活动 加入 {aid_b}", user_id=234567).handle()
        p = self._run(f"/活动 退出 {aid_a}", user_id=234567)
        p.handle()
        self.assertIn("已退出", _sent_text(p))
        self.assertIsNone(self.db.activity.get_member(aid_a, "234567"))
        self.assertIsNotNone(self.db.activity.get_member(aid_b, "234567"))

    def test_multi_submit_by_activity_id(self):
        """多活动下 /提交 <id> 定向到指定活动（无 id 时提示列编号）。"""
        d = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
        self._run("/活动 创建 接龙 甲活动").handle()
        self._run(f"/活动 创建 征集 乙活动 {d}").handle()
        acts = self.db.activity.get_active_activities_for_group(GID)
        aid_a, aid_b = acts[0]["id"], acts[1]["id"]
        self._run("/活动 开始", user_id=123456).handle()
        # 甲（接龙）无成员 → 开始失败；逐个指定开始
        self._run(f"/活动 加入 {aid_a}", user_id=123456).handle()
        self._run(f"/活动 加入 {aid_b}", user_id=123456).handle()
        self._run(f"/活动 开始 {aid_a}", user_id=123456).handle()
        self._run(f"/活动 开始 {aid_b}", user_id=123456).handle()
        self.assertEqual(self.db.activity.get_activity(aid_a)["status"], "running")
        self.assertEqual(self.db.activity.get_activity(aid_b)["status"], "running")

    # ── 征集（collect）──

    def test_collect_create_requires_deadline(self):
        p = self._run("/活动 创建 征集 端午征稿")
        p.handle()
        self.assertIn("截止", _sent_text(p))

    def test_collect_create_and_flow(self):
        d = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
        p = self._run(f"/活动 创建 征集 端午征稿 {d}")
        p.handle()
        self.assertIn("征集活动", _sent_text(p))
        act = self.db.activity.get_active_activity(GID)
        self.assertEqual(act["type"], "collect")
        self.assertEqual(act["deadline"], d + ":00")
        self.assertIsNone(act["hours_per_user"])

        for uid in (123456, 234567):
            self._run("/活动 加入", user_id=uid).handle()
        p = self._run("/活动 开始", user_id=123456)
        p.handle()
        self.assertIn("征集活动", _sent_text(p))
        self.assertIn("开始", _sent_text(p))
        act = self.db.activity.get_active_activity(GID)
        self.assertEqual(act["status"], "running")
        members = self.db.activity.get_members(act["id"])
        # 不建链环：无下家、无计时激活
        self.assertTrue(all(m["next_user_id"] is None for m in members))
        self.assertTrue(all(m["received_at"] is None for m in members))

    def test_collect_single_member_can_start(self):
        d = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
        self._run(f"/活动 创建 征集 独自创作 {d}").handle()
        self._run("/活动 加入", user_id=123456).handle()
        p = self._run("/活动 开始", user_id=123456)
        p.handle()
        self.assertNotIn("至少", _sent_text(p))
        self.assertEqual(self.db.activity.get_active_activity(GID)["status"], "running")

    def test_collect_leave_running_marks_left(self):
        d = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
        self._run(f"/活动 创建 征集 征稿 {d}").handle()
        self._run("/活动 加入", user_id=123456).handle()
        self._run("/活动 加入", user_id=234567).handle()
        self._run("/活动 开始", user_id=123456).handle()
        p = self._run("/活动 退出", user_id=234567)
        p.handle()
        self.assertIn("已退出", _sent_text(p))
        act = self.db.activity.get_active_activity(GID)
        m = self.db.activity.get_member(act["id"], "234567")
        self.assertEqual(m["status"], "left")

    def test_collect_status_shows_progress(self):
        d = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
        self._run(f"/活动 创建 征集 征稿 {d}").handle()
        self._run("/活动 加入", user_id=123456).handle()
        self._run("/活动 开始", user_id=123456).handle()
        p = self._run("/活动 状态")
        p.handle()
        t = _sent_text(p)
        self.assertIn("征集", t)
        self.assertIn("截止", t)



if __name__ == "__main__":
    unittest.main()
