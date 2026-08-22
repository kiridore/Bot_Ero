"""测试抽奖插件 /一键抽奖 与单抽回归。
运行: pytest test/test_lottery_bulk.py
"""
import os
import sys
import sqlite3
import unittest
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.event import Event
from core.db._base import init_schema
from core.db.checkin import CheckinManager
from core.db.lottery import LotteryManager
from core.db.points import PointsManager
from core.db.quest import QuestManager
from core.db.shop import ShopManager
from core.db.titles import TitlesManager
from plugins import lottery as lottery_module
from plugins.lottery import LotteryPlugin
from test.helper import MockApiWrapper, make_group_message, make_private_message

DB_PATH = "/tmp/test_lottery_bulk.db"


class _Db:
    """测试用：仅挂抽奖流程依赖的管理器，跳过真实 DbManager 的全局库。"""
    def __init__(self, conn):
        self.checkin = CheckinManager(conn)
        self.lottery = LotteryManager(conn)
        self.points = PointsManager(conn)
        self.quest = QuestManager(conn)
        self.shop = ShopManager(conn)
        self.titles = TitlesManager(conn)


def _last_text(plugin):
    assert plugin.api.sent_messages, "无消息发送"
    return "".join(
        seg["data"].get("text", "")
        for seg in plugin.api.sent_messages[-1][1]
        if seg["type"] == "text"
    )


def _forward_nodes(plugin):
    """最近一次合并转发的节点列表（每个 node 一条子消息）。"""
    for action, params in reversed(plugin.api.api_calls):
        if action in ("send_group_forward_msg", "send_private_forward_msg"):
            nodes = params["messages"]
            assert nodes and all(n["type"] == "node" for n in nodes)
            return nodes
    raise AssertionError("未发送合并转发消息")


def _node_text(node):
    return "".join(
        seg["data"].get("text", "")
        for seg in node["data"]["content"]
        if seg["type"] == "text"
    )


class TestLotteryBulk(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        self.conn = sqlite3.connect(DB_PATH)
        init_schema(self.conn, self.conn.cursor())
        self.db = _Db(self.conn)
        self.today = datetime.now().strftime("%Y-%m-%d")
        self._orig_draw_reward = lottery_module.draw_reward
        # 固定奖励，保证结果可断言（首抽免费，后续每次 1 积分）
        lottery_module.draw_reward = lambda db, uid: {"type": "points", "value": 2}

    def tearDown(self):
        lottery_module.draw_reward = self._orig_draw_reward
        self.conn.close()

    def _run_raw(self, raw, user_id=123456):
        plugin = LotteryPlugin.__new__(LotteryPlugin)
        plugin.bot_event = Event(raw)
        plugin.api = MockApiWrapper(raw)
        plugin.dbmanager = self.db
        plugin.match("message")
        return plugin

    def _run(self, text_body, user_id=123456):
        return self._run_raw(make_group_message(text_body, user_id=user_id), user_id=user_id)

    def test_bulk_draws_all_remaining_no_checkin(self):
        """未打卡上限 2 次：连抽 2 次，首抽免费、第二次扣 1 积分；
        合并转发为 1 条 header + 每次抽奖各 1 条子消息。"""
        p = self._run("/一键抽奖")
        p.handle()
        nodes = _forward_nodes(p)
        self.assertEqual(len(nodes), 3)  # header + 2 次抽奖
        self.assertIn("一键抽奖完成：共 2 次", _node_text(nodes[0]))
        self.assertEqual(sum("*摇骰子*" in _node_text(n) for n in nodes[1:]), 2)
        for n in nodes:
            self.assertEqual(n["data"]["user_id"], 3915014383)
            self.assertEqual(n["data"]["nickname"], "小埃同学")
        self.assertEqual(self.db.lottery.draw_count(123456, self.today), 2)
        self.assertEqual(self.db.lottery.spent(123456), 1)

    def test_bulk_draws_with_checkin_five(self):
        """今日已打卡上限 5 次：连抽 5 次，扣 4 积分，5 条抽奖子消息。"""
        self.db.checkin.insert(123456, ["test_img"])
        p = self._run("/一键抽奖")
        p.handle()
        nodes = _forward_nodes(p)
        self.assertEqual(len(nodes), 6)  # header + 5 次抽奖
        self.assertEqual(sum("*摇骰子*" in _node_text(n) for n in nodes[1:]), 5)
        self.assertEqual(self.db.lottery.draw_count(123456, self.today), 5)
        self.assertEqual(self.db.lottery.spent(123456), 4)

    def test_bulk_stops_on_insufficient_points(self):
        """奖励为 0 时：免费首抽后积分不足，停止并提示（独立子消息）。"""
        lottery_module.draw_reward = lambda db, uid: {"type": "points", "value": 0}
        p = self._run("/一键抽奖")
        p.handle()
        nodes = _forward_nodes(p)
        self.assertEqual(len(nodes), 3)  # header + 1 次抽奖 + 积分不足提示
        self.assertIn("一键抽奖完成：共 1 次", _node_text(nodes[0]))
        self.assertTrue(any("积分不足" in _node_text(n) for n in nodes))
        self.assertEqual(sum("*摇骰子*" in _node_text(n) for n in nodes), 1)
        self.assertEqual(self.db.lottery.draw_count(123456, self.today), 1)
        self.assertEqual(self.db.lottery.spent(123456), 0)
        self.assertEqual(self.db.points.get(123456), 0)

    def test_bulk_already_exhausted(self):
        """当日次数用完后 /一键抽奖 → 提示已用完（普通消息，非转发）。"""
        self._run("/抽奖").handle()
        self._run("/抽奖").handle()
        p = self._run("/一键抽奖")
        p.handle()
        self.assertIn("今天抽卡次数已用完", _last_text(p))
        self.assertFalse(any(a == "send_group_forward_msg" for a, _ in p.api.api_calls))

    def test_bulk_private_chat_forward(self):
        """私聊走 send_private_forward_msg，节点结构一致。"""
        raw = make_private_message("/一键抽奖", user_id=123456)
        p = self._run_raw(raw, user_id=123456)
        p.handle()
        nodes = _forward_nodes(p)
        self.assertIn("共 2 次", _node_text(nodes[0]))
        self.assertEqual(len(nodes), 3)
        self.assertTrue(any(a == "send_private_forward_msg" for a, _ in p.api.api_calls))

    def test_single_draw_regression(self):
        """/抽奖 单抽行为不变：一条主结果消息，次数与积分结算照旧。"""
        p = self._run("/抽奖")
        p.handle()
        self.assertIn("*摇骰子*", _last_text(p))
        self.assertEqual(self.db.lottery.draw_count(123456, self.today), 1)
        self.assertEqual(self.db.lottery.spent(123456), 0)  # 首抽免费
        self.assertEqual(self.db.points.get(123456), 2)


if __name__ == "__main__":
    unittest.main()
