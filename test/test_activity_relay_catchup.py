"""网页接力提交的补推进逻辑（plugins/activity._relay_catchup）进程内测试。"""

import unittest
from datetime import datetime

from core.database_manager import DbManager
from plugins.activity import _relay_catchup


class StubApi:
    def __init__(self):
        self.calls = []

    def call_api(self, action, params):
        self.calls.append((action, params))
        return 0


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class RelayCatchupTest(unittest.TestCase):
    def setUp(self):
        db = DbManager()
        db.cur.execute("DELETE FROM activity_members")
        db.cur.execute("DELETE FROM activities")
        db.conn.commit()
        self.db = DbManager()
        self.api = StubApi()

    def _mk_relay(self, members_spec):
        aid = self.db.activity.create_activity(
            123, "relay", "接力", None, "999", hours_per_user=48)
        self.db.activity.update_activity(aid, status="running")
        for uid, nick, seq, status, recv in members_spec:
            self.db.activity.add_member(aid, uid, nick)
            fields = {"seq": seq, "status": status}
            if status == "done":
                fields["content"] = f"{uid} 的作品"
                fields["submitted_at"] = _now()
            if recv:
                fields["received_at"] = recv
            self.db.activity.update_member(aid, uid, **fields)
        return aid

    def test_web_submit_advances_next(self):
        aid = self._mk_relay([
            ("111", "甲", 1, "done", _now()),      # 网页提交：done 但未推进
            ("222", "乙", 2, "pending", None),      # 未激活
        ])
        act = self.db.activity.get_activity(aid)
        ok = _relay_catchup(self.api, self.db, act, act["members"])
        self.assertTrue(ok)
        m2 = self.db.activity.get_member(aid, "222")
        self.assertIsNotNone(m2["received_at"], "下一棒应被激活")
        self.db.cur.execute("SELECT status FROM activities WHERE id = ?", (aid,))
        self.assertEqual(self.db.cur.fetchone()[0], "running")
        actions = [c[0] for c in self.api.calls]
        self.assertIn("send_group_msg", actions)

    def test_activated_chain_untouched(self):
        aid = self._mk_relay([
            ("111", "甲", 1, "done", _now()),
            ("222", "乙", 2, "pending", _now()),   # 已激活（bot 流程）
        ])
        act = self.db.activity.get_activity(aid)
        self.assertFalse(_relay_catchup(self.api, self.db, act, act["members"]))
        self.assertEqual(self.api.calls, [])

    def test_chain_tail_finishes(self):
        aid = self._mk_relay([
            ("111", "甲", 1, "done", _now()),
            ("222", "乙", 2, "done", None),         # 链尾网页提交：无 pending
        ])
        act = self.db.activity.get_activity(aid)
        self.assertTrue(_relay_catchup(self.api, self.db, act, act["members"]))
        self.db.cur.execute("SELECT status FROM activities WHERE id = ?", (aid,))
        self.assertEqual(self.db.cur.fetchone()[0], "finished")

    def test_no_done_predecessor_noop(self):
        aid = self._mk_relay([
            ("111", "甲", 1, "pending", None),      # 开始即异常态：不动作
            ("222", "乙", 2, "pending", None),
        ])
        act = self.db.activity.get_activity(aid)
        self.assertFalse(_relay_catchup(self.api, self.db, act, act["members"]))
        self.assertEqual(self.api.calls, [])


if __name__ == "__main__":
    unittest.main()
