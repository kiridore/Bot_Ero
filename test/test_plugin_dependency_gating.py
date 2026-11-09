"""config-unification 任务组2：跨插件写入不能绕过目标功能开关。

合并后兑换码由网页个人主页承接（`webapp/profile/redeem_service.py`），
依赖门控在核销前检查部署允许范围与账号/私聊插件开关。
"""
import tempfile
import unittest
from pathlib import Path

from core import config
from core.database_manager import DbManager
from plugins.who_is_spy.titles import grant_game_titles


class RedeemCodeDependencyTest(unittest.TestCase):
    """目标功能未开放时整次拒绝：不核销、不发部分奖励；开启后可正常兑换。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_db = config.DB_PATH
        self._old_allowed = config.ALLOWED_PLUGINS_CONF
        config.DB_PATH = Path(self._tmp.name) / "dep.db"
        config.ALLOWED_PLUGINS_CONF = None  # 允许全部，全靠账号开关控制
        db = DbManager()
        db.conn.close()

    def tearDown(self):
        config.DB_PATH = self._old_db
        config.ALLOWED_PLUGINS_CONF = self._old_allowed
        self._tmp.cleanup()

    def _set_title_enabled(self, enabled):
        db = DbManager()
        try:
            with db.conn:
                db.conn.execute("DELETE FROM group_plugin_config WHERE group_id = 0")
                if enabled:
                    db.conn.execute(
                        "INSERT INTO group_plugin_config (group_id, plugin_name) VALUES (0, 'title')")
        finally:
            db.conn.close()

    def _count_usage(self):
        db = DbManager()
        try:
            return db.conn.execute("SELECT COUNT(*) FROM redeem_code_usage").fetchone()[0]
        finally:
            db.conn.close()

    def _titles(self, user_id):
        db = DbManager()
        try:
            return db.titles.list(user_id)
        finally:
            db.conn.close()

    def test_title_closed_rejects_whole_redemption(self):
        from webapp.profile import redeem_service

        self._set_title_enabled(False)
        with self.assertRaises(ValueError) as ctx:
            redeem_service.redeem_code("42", "TEST-CODE-TEST")
        self.assertIn("未开放", str(ctx.exception))
        self.assertEqual(self._count_usage(), 0)   # 未核销
        self.assertFalse(self._titles("42"))       # 无部分奖励

        self._set_title_enabled(True)              # 开启后同一码可正常兑换
        redeem_service.redeem_code("42", "TEST-CODE-TEST")
        self.assertEqual(self._count_usage(), 1)
        self.assertTrue(self._titles("42"))


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
        conn = self.db.conn
        # 结算奖励与结束记录同事务（titles 要求），这里显式开启事务模拟结算。
        conn.execute("BEGIN")
        granted_off = grant_game_titles(self.db, "7", "spy", "spy", allow_titles=False)
        conn.commit()
        granted_on = []
        conn.execute("BEGIN")
        for _ in range(10):  # 达到 civilian_wins 阈值 10 → 解锁 306
            granted_on = grant_game_titles(self.db, "8", "civilian", "civilian", allow_titles=True)
        conn.commit()
        row = conn.execute(
            "SELECT total_games, spy_wins FROM user_game_stats WHERE user_id='7'").fetchone()
        self.assertEqual(tuple(row), (1, 1))           # 战绩照记
        self.assertEqual(granted_off, [])             # 不发新称号
        self.assertFalse(self.db.titles.list("7"))
        self.assertTrue(granted_on or self.db.titles.list("8"))  # 开启时正常解锁
