"""config-unification 任务组2：跨插件写入不能绕过目标功能开关。"""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from core import config
from core.database_manager import DbManager
from core.event import Event
from core.plugin_dispatch import Operation
from core.message_output import MessageOutput
from plugins.redeem_code import RedeemCodePlugin
from plugins.who_is_spy.titles import grant_game_titles


class RedeemCodeDependencyTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_db = config.DB_PATH
        config.DB_PATH = Path(self._tmp.name) / "dep.db"
        self.db = DbManager()
        self.db.conn.executescript("""
            CREATE TABLE IF NOT EXISTS redeem_code_claims (
                user_id INTEGER NOT NULL, code TEXT NOT NULL, claimed_at TEXT,
                PRIMARY KEY (user_id, code));
        """)
        self.db.conn.commit()

    def tearDown(self):
        self.db.conn.close()
        config.DB_PATH = self._old_db
        self._tmp.cleanup()

    def _run(self, enabled):
        raw = {"post_type": "message", "message_type": "private", "user_id": 42,
               "message_id": 7, "message": [{"type": "text", "data": {"text": "/兑换码 TEST-CODE-TEST"}}]}
        sent = []
        op = Operation({"redeem_code": True, "title": enabled},
                       MessageOutput(lambda r: sent.append(r.content) or 1, ("private", 42)))
        p = RedeemCodePlugin.__new__(RedeemCodePlugin)
        p.bot_event, p.dbmanager, p.operation = Event(raw), self.db, op
        p.api = Mock()
        p.api.send_msg.side_effect = lambda *segs: sent.append(
            "".join(seg["data"].get("text", "") for seg in segs)) or 1
        p.args = ["TEST-CODE-TEST"]
        op.execute("redeem_code", p.handle)
        op.finish()
        return sent

    def test_title_closed_rejects_whole_redemption(self):
        sent = self._run(False)
        self.assertTrue(any("未开放" in s for s in sent))
        self.assertEqual(self.db.conn.execute(
            "SELECT COUNT(*) FROM redeem_code_claims").fetchone()[0], 0)  # 未核销
        self.assertFalse(self.db.titles.list(42))                      # 无部分奖励
        sent2 = self._run(True)  # 开启后同一码可正常兑换
        self.assertTrue(any("兑换成功" in s for s in sent2))
        self.assertTrue(self.db.titles.list(42))


class SpyTitleDependencyTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_db = config.DB_PATH
        config.DB_PATH = Path(self._tmp.name) / "spy.db"
        self.db = DbManager()

    def tearDown(self):
        self.db.conn.close()
        config.DB_PATH = self._old_db
        self._tmp.cleanup()

    def test_stats_recorded_without_titles_when_disabled(self):
        granted_off = grant_game_titles(self.db, "7", "spy", "spy", allow_titles=False)
        granted_on = []
        for _ in range(10):  # 达到 civilian_wins 阈值 10 → 解锁 306
            granted_on = grant_game_titles(self.db, "8", "civilian", "civilian", allow_titles=True)
        row = self.db.conn.execute(
            "SELECT total_games, spy_wins FROM user_game_stats WHERE user_id='7'").fetchone()
        self.assertEqual(tuple(row), (1, 1))           # 战绩照记
        self.assertEqual(granted_off, [])             # 不发新称号
        self.assertFalse(self.db.titles.list("7"))
        self.assertTrue(granted_on or self.db.titles.list("8"))  # 开启时正常解锁
