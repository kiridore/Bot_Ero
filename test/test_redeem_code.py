"""测试兑换码插件。
运行: python test/test_redeem_code.py
"""
import os
import sys
import sqlite3
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.event import Event
from core.db._base import init_schema
from core.db.points import PointsManager
from core.db.redeem import RedeemManager
from core.db.titles import TitlesManager
from core.utils import add_user_point
from plugins.redeem_code import RedeemCodePlugin
from plugins.redeem_code import codes
from test.helper import MockApiWrapper, make_group_message

DB_PATH = "/tmp/test_redeem_code.db"


class _Db:
    """测试用：仅挂兑换码/称号/积分管理器，跳过真实 DbManager 的全局库。"""
    def __init__(self, conn):
        self.redeem = RedeemManager(conn)
        self.titles = TitlesManager(conn)
        self.points = PointsManager(conn)


def _sent_text(plugin):
    assert plugin.api.sent_messages, "无消息发送"
    # 成功回复以 at 段开头，汇总所有 text 段文本
    return "".join(
        seg["data"].get("text", "")
        for seg in plugin.api.sent_messages[-1][1]
        if seg["type"] == "text"
    )


def _usage_count(conn, user_id, code=None):
    if code is None:
        cur = conn.execute(
            "SELECT COUNT(*) FROM redeem_code_usage WHERE user_id = ?",
            (user_id,),
        )
    else:
        cur = conn.execute(
            "SELECT COUNT(*) FROM redeem_code_usage WHERE user_id = ? AND code = ?",
            (user_id, code),
        )
    return cur.fetchone()[0]


class TestRedeemCode(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        self.conn = sqlite3.connect(DB_PATH)
        init_schema(self.conn, self.conn.cursor())
        self.db = _Db(self.conn)

    def tearDown(self):
        self.conn.close()

    def _run(self, text_body, user_id=123456):
        raw = make_group_message(text_body, user_id=user_id)
        plugin = RedeemCodePlugin.__new__(RedeemCodePlugin)
        plugin.bot_event = Event(raw)
        plugin.api = MockApiWrapper(raw)
        plugin.dbmanager = self.db
        plugin.match("message")  # CommandPlugin 填充 self.args
        return plugin

    def test_redeem_unlocks_tester_title(self):
        p = self._run("/兑换码 TEST-CODE-TEST")
        p.handle()
        reply = _sent_text(p)
        self.assertIn("兑换成功", reply)
        self.assertIn("测试员", reply)
        self.assertTrue(self.db.titles.has(123456, 501))

    def test_second_use_blocked(self):
        self._run("/兑换码 TEST-CODE-TEST").handle()
        p = self._run("/兑换码 TEST-CODE-TEST")
        p.handle()
        self.assertIn("已使用过", _sent_text(p))
        self.assertEqual(_usage_count(self.conn, 123456, "TEST-CODE-TEST"), 1)

    def test_different_user_can_use(self):
        self._run("/兑换码 TEST-CODE-TEST").handle()
        p = self._run("/兑换码 TEST-CODE-TEST", user_id=234567)
        p.handle()
        self.assertIn("兑换成功", _sent_text(p))
        self.assertTrue(self.db.titles.has(234567, 501))

    def test_lowercase_input_normalized(self):
        p = self._run("/兑换码 test-code-test")
        p.handle()
        self.assertIn("兑换成功", _sent_text(p))
        self.assertTrue(self.db.titles.has(123456, 501))
        self.assertEqual(_usage_count(self.conn, 123456, "TEST-CODE-TEST"), 1)

    def test_invalid_format(self):
        p = self._run("/兑换码 AAAA-BBBB-CC")
        p.handle()
        self.assertIn("格式不正确", _sent_text(p))
        self.assertEqual(_usage_count(self.conn, 123456), 0)

    def test_unknown_code(self):
        p = self._run("/兑换码 AAAA-BBBB-CCCC")
        p.handle()
        self.assertIn("不存在或已失效", _sent_text(p))
        self.assertEqual(_usage_count(self.conn, 123456), 0)

    def test_callback_failure_rolls_back(self):
        def _boom(db, user_id, api):
            raise RuntimeError("boom")

        codes.REDEEM_CODES["FAIL-CODE-TEST"] = {
            "description": "回调失败测试",
            "callback": _boom,
        }
        try:
            p = self._run("/兑换码 FAIL-CODE-TEST")
            p.handle()
            self.assertIn("处理失败", _sent_text(p))
            self.assertEqual(_usage_count(self.conn, 123456), 0)
        finally:
            del codes.REDEEM_CODES["FAIL-CODE-TEST"]

    def test_combo_callback_points_and_title(self):
        def _combo(db, user_id, api):
            add_user_point(db, user_id, 100)
            db.titles.unlock(user_id, 501)
            return "积分 +100，解锁称号：「测试员」"

        codes.REDEEM_CODES["COMB-CODE-TEST"] = {
            "description": "积分+称号组合测试",
            "callback": _combo,
        }
        try:
            p = self._run("/兑换码 COMB-CODE-TEST")
            p.handle()
            reply = _sent_text(p)
            self.assertIn("兑换成功", reply)
            self.assertIn("积分 +100", reply)
            self.assertIn("测试员", reply)
            self.assertEqual(self.db.points.get(123456), 100)
            self.assertTrue(self.db.titles.has(123456, 501))
        finally:
            del codes.REDEEM_CODES["COMB-CODE-TEST"]


    def test_first_anniversary_code_grants_title_and_points(self):
        p = self._run("/兑换码 ONLY-YEAR-ONCE")
        p.handle()
        reply = _sent_text(p)
        self.assertIn("兑换成功", reply)
        self.assertIn("1st", reply)
        self.assertIn("+10", reply)
        self.assertTrue(self.db.titles.has(123456, 502))
        self.assertEqual(self.db.points.get(123456), 10)
        self.assertEqual(_usage_count(self.conn, 123456, "ONLY-YEAR-ONCE"), 1)

    def test_first_anniversary_code_second_use_blocked(self):
        self._run("/兑换码 ONLY-YEAR-ONCE").handle()
        p = self._run("/兑换码 ONLY-YEAR-ONCE")
        p.handle()
        self.assertIn("已使用过", _sent_text(p))
        self.assertEqual(self.db.points.get(123456), 10)  # 积分不重复发放
        self.assertEqual(_usage_count(self.conn, 123456, "ONLY-YEAR-ONCE"), 1)


if __name__ == "__main__":
    unittest.main()
