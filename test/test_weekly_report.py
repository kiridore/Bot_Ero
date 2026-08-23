"""周报生成日志覆盖校验测试。

背景：2026-08-16 周报功能上线，启动补偿曾为消息日志未覆盖的历史周（2026-08-03 /
2026-08-10 两期）生成空/残缺周报。_generate_week 现要求日志最早一条消息不晚于周
起点，否则跳过——上线前整周与上线当周均不出报，首个完整周成为第 1 期。

运行: pytest test/test_weekly_report.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import GROUP_ID
from core.db.message_log import MessageLogManager
from plugins.weekly_report import WeeklyReportPlugin
from test.helper import MockApiWrapper, make_group_message

# 周报功能上线当晚（2026-08-16 周日 17:48）首条进入日志的消息
EARLIEST = "2026-08-16 17:48:00"


class TestEarliestSentAt(unittest.TestCase):
    def setUp(self):
        self.mlog = MessageLogManager()
        self.mlog.cur.execute("DELETE FROM messages")
        self.mlog.conn.commit()

    def tearDown(self):
        self.mlog.cur.execute("DELETE FROM messages")
        self.mlog.conn.commit()
        self.mlog.close()

    def test_empty_log_returns_none(self):
        self.assertIsNone(self.mlog.earliest_sent_at(int(GROUP_ID)))

    def test_returns_min_not_insert_order(self):
        self.mlog.insert(int(GROUP_ID), 1, 101, "2026-08-20 09:00:00", "晚插入但时间靠后")
        self.mlog.insert(int(GROUP_ID), 2, 102, EARLIEST, "晚插入但时间靠前")
        self.assertEqual(self.mlog.earliest_sent_at(int(GROUP_ID)), EARLIEST)


class TestGenerateWeekCoverageGate(unittest.TestCase):
    def setUp(self):
        mlog = MessageLogManager()
        mlog.cur.execute("DELETE FROM messages")
        mlog.insert(int(GROUP_ID), 10001, 1, EARLIEST, "功能上线当晚的消息")
        mlog.insert(int(GROUP_ID), 10001, 2, "2026-08-20 12:00:00", "首个完整周内的消息")
        mlog.conn.commit()
        mlog.close()

        self.plugin = WeeklyReportPlugin(make_group_message("meta"))
        self.plugin.api = MockApiWrapper(make_group_message("meta"))
        self.db = self.plugin.dbmanager
        self.db.cur.execute("DELETE FROM weekly_reports")
        self.db.conn.commit()

    def tearDown(self):
        self.db.cur.execute("DELETE FROM weekly_reports")
        self.db.conn.commit()

    def _row(self, week_key):
        return self.db.weekly.get(week_key, int(GROUP_ID))

    def test_weeks_not_covered_by_log_skipped(self):
        # 上线前整周（日志完全不存在）与上线当周（仅约 14 小时日志）都不出报
        self.plugin._generate_week("2026-08-03 08:00:00", "2026-08-10 08:00:00")
        self.plugin._generate_week("2026-08-10 08:00:00", "2026-08-17 08:00:00")
        self.assertIsNone(self._row("2026-08-03"))
        self.assertIsNone(self._row("2026-08-10"))

    def test_empty_log_skips_everything(self):
        mlog = MessageLogManager()
        mlog.cur.execute("DELETE FROM messages")
        mlog.conn.commit()
        mlog.close()
        self.plugin._generate_week("2026-08-17 08:00:00", "2026-08-24 08:00:00")
        self.assertIsNone(self._row("2026-08-17"))

    def test_first_covered_week_becomes_issue_1(self):
        self.plugin._generate_week("2026-08-17 08:00:00", "2026-08-24 08:00:00")
        row = self._row("2026-08-17")
        self.assertIsNotNone(row)
        self.assertEqual(row["data_json"]["period"]["issue"], 1)

    def test_generate_is_idempotent(self):
        for _ in range(2):
            self.plugin._generate_week("2026-08-17 08:00:00", "2026-08-24 08:00:00")
        rows = self.db.weekly.list(int(GROUP_ID))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["data_json"]["period"]["issue"], 1)
