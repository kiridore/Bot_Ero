"""打卡私聊标记回归：私聊/群聊写入 is_private 列，事件 data 带 private 标记。
运行: pytest test/test_checkin_privacy.py
"""
import os
import sys
import sqlite3
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import test.helper  # noqa: F401  桩掉 core.api.WS_APP，必须在导入插件前执行

from core.event import Event
from core.db._base import init_schema
from core.db.checkin import CheckinManager
from core.db.lottery import LotteryManager
from core.db.points import PointsManager
from core.db.quest import QuestManager
from core.db.shop import ShopManager
from core.db.titles import TitlesManager
from plugins.checkin import CheckinPlugin
from test.helper import MockApiWrapper, make_group_message, make_private_message

DB_PATH = "/tmp/test_checkin_privacy.db"


class _Db:
    """checkin 插件 handle 全链路所需管理器（照 test_lottery_bulk 模式）。"""
    def __init__(self, conn):
        self.checkin = CheckinManager(conn)
        self.lottery = LotteryManager(conn)
        self.points = PointsManager(conn)
        self.quest = QuestManager(conn)
        self.shop = ShopManager(conn)
        self.titles = TitlesManager(conn)


def _with_image(raw: dict, filename: str) -> dict:
    # /打卡 无图片时直接拒绝（"没有图片是没办法打卡的喵"），必须带 image 段走完整 handle
    raw["message"] = raw["message"] + [{"type": "image", "data": {"file": filename}}]
    return raw


class TestCheckinPrivateFlag(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        self.conn = sqlite3.connect(DB_PATH)
        init_schema(self.conn, self.conn.cursor())
        self.db = _Db(self.conn)
        self._emitted = []
        import plugins.checkin as m
        self._orig_emit = m.emit_event
        m.emit_event = lambda **kw: self._emitted.append(kw)

    def tearDown(self):
        import plugins.checkin as m
        m.emit_event = self._orig_emit
        self.conn.close()

    def _run(self, raw):
        plugin = CheckinPlugin.__new__(CheckinPlugin)
        plugin.bot_event = Event(raw)
        plugin.api = MockApiWrapper(raw)
        plugin.api.get_image = lambda name: ""  # 图片即时下载走 clean failed 分支
        plugin.dbmanager = self.db
        plugin.match("message")
        plugin.handle()
        return plugin

    def _flag(self, user_id):
        return self.conn.execute(
            "SELECT is_private FROM checkin_records WHERE user_id = ?", (user_id,)
        ).fetchone()[0]

    def test_private_checkin_flagged(self):
        raw = _with_image(make_private_message("/打卡", user_id=111), "AAA111.image")
        self._run(raw)
        self.assertEqual(self._flag(111), 1)
        self.assertTrue(self._emitted[-1]["data"]["private"])

    def test_group_checkin_not_flagged(self):
        raw = _with_image(make_group_message("/打卡", user_id=222), "BBB222.image")
        self._run(raw)
        self.assertEqual(self._flag(222), 0)
        self.assertFalse(self._emitted[-1]["data"]["private"])

    def test_event_images_unchanged_plus_private_key(self):
        raw = _with_image(make_private_message("/打卡", user_id=333), "x{y}-z.image")
        self._run(raw)
        data = self._emitted[-1]["data"]
        self.assertEqual(data["images"], ["/thumb/333/xyz.image"])
        self.assertIn("private", data)


if __name__ == "__main__":
    unittest.main()
