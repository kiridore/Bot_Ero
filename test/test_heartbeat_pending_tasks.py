"""config-unification 任务组3：关闭期间记录保留与恢复后的重复执行防护（AC04）。"""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import config
from core import context as runtime_context
from core.database_manager import DbManager


class PendingTaskTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_db = config.DB_PATH
        config.DB_PATH = Path(self._tmp.name) / "pending.db"
        self.db = DbManager()
        self.api = Mock()

    def tearDown(self):
        self.db.conn.close()
        config.DB_PATH = self._old_db
        self._tmp.cleanup()

    def _enable_alarm(self, gid):
        self.db.conn.execute(
            "INSERT OR IGNORE INTO group_plugin_config VALUES (?, 'group_alarm')", (gid,))
        self.db.conn.commit()

    def _run_alarm(self):
        from plugins.group_alarm import GroupAlarmPlugin
        p = GroupAlarmPlugin.__new__(GroupAlarmPlugin)
        p.dbmanager, p.api = self.db, self.api
        p._handle_meta_due()

    def test_backlog_alarm_fires_once_after_reenable_no_duplicates(self):
        self.db.alarm.add(7, datetime.now() - timedelta(days=2), "过期提醒", group_id=100)
        self._run_alarm()  # 未启用：保留
        self.assertEqual(
            self.db.conn.execute("SELECT fired FROM group_alarms").fetchone()[0], 0)
        self._enable_alarm(100)
        self._run_alarm()  # 重新开启：按原到期规则处理积压
        self.assertEqual(
            self.db.conn.execute("SELECT fired FROM group_alarms").fetchone()[0], 1)
        self._run_alarm()  # 重复执行防护：不重复发送
        self.assertEqual(self.api.call_api.call_count, 1)

    def test_disabled_immortal_keeps_bets_and_assets_untouched(self):
        from plugins.immortal_lottery import ImmortalLotteryPlugin
        from plugins.immortal_lottery.helpers import _sunday_draw_period_monday, _period_key_from_monday
        from plugins.immortal_lottery import _now_bj
        pk = _period_key_from_monday(_sunday_draw_period_monday(_now_bj().date()))
        self.db.points.set(5, 10)
        self.db.conn.execute(
            "INSERT INTO immortal_lottery_bets (group_id, period_key, user_id, digits, bet_bj_date, created_at)"
            " VALUES (100, ?, 5, '1234', '2026-01-01', ?)",
            (pk, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.db.conn.commit()
        p = ImmortalLotteryPlugin.__new__(ImmortalLotteryPlugin)
        p.dbmanager, p.api = self.db, self.api
        p._handle_draw_tick()  # 群 100 未启用
        self.assertEqual(self.db.conn.execute(
            "SELECT COUNT(*) FROM immortal_lottery_results").fetchone()[0], 0)  # 未开奖
        self.assertEqual(self.db.points.get(5), 10)   # 不退款、不动资金
        kept = self.db.conn.execute(
            "SELECT COUNT(*) FROM immortal_lottery_bets").fetchone()[0]
        self.assertEqual(kept, 1)                     # 待结算注单保留可定位


if __name__ == "__main__":
    unittest.main(verbosity=2)
