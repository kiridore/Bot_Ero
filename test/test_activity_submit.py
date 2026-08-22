"""测试活动私聊提交与流转。
运行: pytest test/test_activity_submit.py
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
from test.helper import MockApiWrapper, make_private_message, make_group_message

DB_PATH = "/tmp/test_activity_submit.db"
GID = 296470819


class _Db:
    def __init__(self, conn):
        self.activity = ActivityManager(conn)


def _setup_activity(db, type_):
    aid = db.activity.create_activity(
        GID, type_, "t", None, "1",
        hours_per_user=24.0 if type_ == "relay" else None,
        deadline=None if type_ == "relay" else "2026-09-15 20:00:00",
    )
    for uid, nick in (("100", "A"), ("200", "B"), ("300", "C")):
        db.activity.add_member(aid, uid, nick)
    db.activity.update_activity(aid, status="running")
    if type_ == "relay":
        db.activity.set_ring(aid, [("100", "200", 1), ("200", "300", 2), ("300", None, 3)])
    else:
        db.activity.set_ring(aid, [("100", "200", 1), ("200", "300", 2), ("300", "100", 3)])
    return aid


class TestSubmit(unittest.TestCase):
    def setUp(self):
        for p in (DB_PATH, "/tmp/test_activity_archive_submit"):
            if os.path.exists(p):
                if os.path.isdir(p):
                    import shutil; shutil.rmtree(p)
                else:
                    os.remove(p)
        self.conn = sqlite3.connect(DB_PATH)
        init_schema(self.conn, self.conn.cursor())
        self.db = _Db(self.conn)
        context.python_data_path = "/tmp/test_activity_archive_submit"

    def tearDown(self):
        self.conn.close()

    def _submit(self, user_id, text_body="", arg=""):
        full = f"/提交 {arg}".strip() + (f" {text_body}" if text_body else "")
        raw = make_private_message("", user_id=user_id)
        raw["message"] = [{"type": "text", "data": {"text": full}}]
        plugin = ActivityPlugin.__new__(ActivityPlugin)
        plugin.bot_event = Event(raw)
        plugin.api = MockApiWrapper(raw)
        plugin.dbmanager = self.db
        return plugin

    def _group_leave(self, user_id):
        raw = make_group_message("/活动 退出", user_id=user_id, group_id=GID)
        plugin = ActivityPlugin.__new__(ActivityPlugin)
        plugin.bot_event = Event(raw)
        plugin.api = MockApiWrapper(raw)
        plugin.dbmanager = self.db
        return plugin

    def _group_announce_texts(self, plugin) -> str:
        return "".join(
            seg["data"]["text"]
            for a, c in plugin.api.api_calls if a == "send_group_msg"
            for seg in c["message"] if seg["type"] == "text"
        )

    def test_relay_flow(self):
        aid = _setup_activity(self.db, "relay")
        p = self._submit(100, "第一章作品")
        p.handle()
        m = self.db.activity.get_member(aid, "100")
        self.assertEqual(m["status"], "done")
        self.assertEqual(m["content"], "第一章作品")
        b = self.db.activity.get_member(aid, "200")
        self.assertIsNotNone(b["received_at"])          # 顺延并开始计时
        # B 收到了接力作品（私聊转发）
        fwd = [c for a, c in p.api.api_calls if a == "send_private_msg"]
        self.assertTrue(any(c["user_id"] == 200 for c in fwd))

    def test_submit_wrong_turn(self):
        aid = _setup_activity(self.db, "relay")
        self._submit(200, "抢先").handle()
        self.assertEqual(self.db.activity.get_member(aid, "200")["status"], "pending")

    def test_match_submit_no_forward(self):
        """匹配提交：机器人不转发（玩家自提），仅记录+群公告。"""
        aid = _setup_activity(self.db, "match")
        p = self._submit(100, "给B的礼物")
        p.handle()
        m = self.db.activity.get_member(aid, "100")
        self.assertEqual(m["status"], "done")
        self.assertEqual(m["content"], "给B的礼物")
        fwd = [c for a, c in p.api.api_calls if a == "send_private_msg"]
        self.assertFalse(fwd, "匹配提交后不应有私聊转发")
        texts = "".join(
            seg["data"]["text"] for a, m in p.api.sent_messages
            for seg in m if seg["type"] == "text")
        self.assertIn("提交成功", texts)
        self.assertIn("A 提交了作品", self._group_announce_texts(p))

    def test_duplicate_submit_overwrites(self):
        """重复提交覆盖前一版（接龙：已提交成员可随时覆盖自己的提交）。"""
        aid = _setup_activity(self.db, "relay")
        p1 = self._submit(100, "第一版")
        p1.handle()
        p2 = self._submit(100, "第二版")
        p2.handle()
        m = self.db.activity.get_member(aid, "100")
        self.assertEqual(m["content"], "第二版")        # 覆盖
        texts = "".join(
            seg["data"]["text"] for a, mm in p2.api.sent_messages
            for seg in mm if seg["type"] == "text")
        self.assertIn("已更新", texts)

    def test_duplicate_submit_match_no_finish_no_announce(self):
        """匹配覆盖提交：不触发结束、不重复群公告。"""
        aid = _setup_activity(self.db, "match")
        self._submit(100, "第一版").handle()
        p2 = self._submit(100, "第二版")
        p2.handle()
        m = self.db.activity.get_member(aid, "100")
        self.assertEqual(m["content"], "第二版")
        self.assertEqual(self.db.activity.get_activity(aid)["status"], "running")
        texts = self._group_announce_texts(p2)
        self.assertNotIn("提交了作品", texts)             # 更新不重复公告

    def test_duplicate_submit_relay_no_reforward(self):
        """接龙覆盖提交：不重复转发给下一位。"""
        aid = _setup_activity(self.db, "relay")
        self._submit(100, "第一版").handle()
        p2 = self._submit(100, "第二版")
        p2.handle()
        fwd = [c for a, c in p2.api.api_calls if a == "send_private_msg"]
        self.assertFalse(fwd, "覆盖提交不应再次转发")
        self.assertEqual(self.db.activity.get_member(aid, "200")["status"], "pending")

    def test_submit_finishes_relay(self):
        aid = _setup_activity(self.db, "relay")
        for uid, content in ((100, "一"), (200, "二"), (300, "三")):
            self._submit(uid, content).handle()
        act = self.db.activity.get_activity(aid)
        self.assertEqual(act["status"], "finished")
        d = f"/tmp/test_activity_archive_submit/activity_archive/{aid}"
        self.assertTrue(os.path.isfile(f"{d}/relay.md"))

    def test_submit_match_stays_running(self):
        """匹配全员提交：不自动结束（可反复覆盖修改），等待截止/手动结束。"""
        aid = _setup_activity(self.db, "match")
        for uid, content in ((100, "一"), (200, "二"), (300, "三")):
            self._submit(uid, content).handle()
        act = self.db.activity.get_activity(aid)
        self.assertEqual(act["status"], "running")
        d = f"/tmp/test_activity_archive_submit/activity_archive/{aid}"
        self.assertFalse(os.path.exists(d), "全员提交后不应归档")

    def test_match_all_submitted_no_forward(self):
        """环 A→B→C→A 全员提交：活动保持进行，全程无私聊转发。"""
        aid = _setup_activity(self.db, "match")
        p = None
        for uid, content in ((100, "一"), (200, "二"), (300, "三")):
            p = self._submit(uid, content)
            p.handle()
        act = self.db.activity.get_activity(aid)
        self.assertEqual(act["status"], "running")
        fwd = [c for a, c in p.api.api_calls if a == "send_private_msg"]
        self.assertFalse(fwd, "匹配提交全程不应有私聊转发")

    def test_match_revise_after_all_submitted(self):
        """全员提交后仍可覆盖修改（核心诉求：保留修改机会）。"""
        aid = _setup_activity(self.db, "match")
        for uid, content in ((100, "一"), (200, "二"), (300, "三")):
            self._submit(uid, content).handle()
        p = self._submit(100, "修改版")
        p.handle()
        m = self.db.activity.get_member(aid, "100")
        self.assertEqual(m["content"], "修改版")
        self.assertEqual(self.db.activity.get_activity(aid)["status"], "running")

    def test_leave_running_relay_advances(self):
        """进行中退出（轮到 B 时）：B 标记 left 且链顺延给 C（Task 4 死分支修复验证）。"""
        aid = _setup_activity(self.db, "relay")
        self._submit(100, "第一章作品").handle()        # A 完成 → B 成为当前棒
        self._group_leave(200).handle()                 # B 轮到中退出
        b = self.db.activity.get_member(aid, "200")
        self.assertEqual(b["status"], "left")
        c = self.db.activity.get_member(aid, "300")
        self.assertIsNotNone(c["received_at"])          # 链已顺延到 C
        self.assertEqual(self.db.activity.get_activity(aid)["status"], "running")

    def test_match_leave_then_all_submitted_stays_running(self):
        """匹配环中有人退出后，剩余成员全员提交仍保持进行（可修改，截止才结束）。"""
        aid = _setup_activity(self.db, "match")
        self._group_leave(200).handle()                 # B 退出 → A.next 改为 C
        self._submit(100, "给C的礼物").handle()
        self._submit(300, "给A的礼物").handle()
        act = self.db.activity.get_activity(aid)
        self.assertEqual(act["status"], "running")


if __name__ == "__main__":
    unittest.main()
