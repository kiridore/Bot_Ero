"""周报生成日志覆盖校验测试。

背景：2026-08-16 周报功能上线，启动补偿曾为消息日志未覆盖的历史周（2026-08-03 /
2026-08-10 两期）生成空/残缺周报。_generate_week 现要求日志最早一条消息不晚于周
起点，否则跳过——上线前整周与上线当周均不出报，首个完整周成为第 1 期。

运行: pytest test/test_weekly_report.py
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.base import TimedHeartbeatPlugin
from core.config import GROUP_ID
from core.db.message_log import MessageLogManager
from plugins.weekly_report import WeeklyReportPlugin
import plugins.weekly_report as weekly_report
from test.helper import MockApiWrapper, make_group_message

# 周报功能上线当晚（2026-08-16 周日 17:48）首条进入日志的消息
EARLIEST = "2026-08-16 17:48:00"


class _FixedDatetime(datetime):
    """冻结 today()/now() 的 datetime 替身（strptime 等继承真类，其余行为不变）。"""

    _fixed = datetime(2026, 8, 24, 8, 0, 30)

    @classmethod
    def today(cls):
        return cls._fixed

    @classmethod
    def now(cls, tz=None):
        return cls._fixed


def _freeze(moment: datetime) -> type[datetime]:
    _FixedDatetime._fixed = moment
    return _FixedDatetime


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


class TestTriggerWiring(unittest.TestCase):
    """回归：match() 已消费 08:00 分钟去重标记后，handle() 不得再次查询
    should_run_on_heartbeat——旧实现二次调用恒为 False，周一 08:00 定时生成
    从未生效，上线首周全靠启动补漏生成掩盖了该缺陷。"""

    def setUp(self):
        mlog = MessageLogManager()
        mlog.cur.execute("DELETE FROM messages")
        mlog.insert(int(GROUP_ID), 10001, 1, EARLIEST, "功能上线当晚的消息")
        mlog.insert(int(GROUP_ID), 10001, 2, "2026-08-20 12:00:00", "结算周内的消息")
        mlog.conn.commit()
        mlog.close()

        weekly_report._boot_checked = True  # 模拟进程已运行，排除启动补漏分支
        TimedHeartbeatPlugin._last_run_minute.pop("WeeklyReportPlugin", None)

        self.plugin = WeeklyReportPlugin(make_group_message("meta"))
        self.plugin.api = MockApiWrapper(make_group_message("meta"))
        self.db = self.plugin.dbmanager
        self.db.cur.execute("DELETE FROM weekly_reports")
        self.db.conn.commit()

    def tearDown(self):
        self.db.cur.execute("DELETE FROM weekly_reports")
        self.db.conn.commit()
        weekly_report._boot_checked = True
        TimedHeartbeatPlugin._last_run_minute.pop("WeeklyReportPlugin", None)

    def test_scheduled_monday_0800_generates_last_week(self):
        monday_0800 = datetime(2026, 8, 24, 8, 0, 30)
        with patch("core.base.datetime", _freeze(monday_0800)):
            self.assertTrue(self.plugin.match("meta"))  # 消费 08:00 分钟标记
        with patch("core.utils.datetime", _freeze(monday_0800)):
            self.plugin.handle()
        row = self.db.weekly.get("2026-08-17", int(GROUP_ID))
        self.assertIsNotNone(row)
        self.assertEqual(row["data_json"]["period"]["issue"], 1)

    def test_boot_compensation_after_settlement_generates_last_week(self):
        weekly_report._boot_checked = False
        monday_0900 = datetime(2026, 8, 24, 9, 0, 0)
        self.assertTrue(self.plugin.match("meta"))
        with patch("core.utils.datetime", _freeze(monday_0900)):
            self.plugin.handle()
        self.assertTrue(weekly_report._boot_checked)
        row = self.db.weekly.get("2026-08-17", int(GROUP_ID))
        self.assertIsNotNone(row)

    def test_boot_compensation_before_coverage_still_blocked(self):
        weekly_report._boot_checked = False
        sunday_night = datetime(2026, 8, 23, 20, 0, 0)
        self.assertTrue(self.plugin.match("meta"))
        with patch("core.utils.datetime", _freeze(sunday_night)):
            self.plugin.handle()
        self.assertTrue(weekly_report._boot_checked)
        self.assertEqual(self.db.weekly.list(int(GROUP_ID)), [])


class TestImmortalInReport(unittest.TestCase):
    """仙人彩中奖明细进周报：winners 按奖级列中奖人/号码；有人 ≥3A 时头条为大奖落定。"""

    def setUp(self):
        mlog = MessageLogManager()
        mlog.cur.execute("DELETE FROM messages")
        mlog.insert(int(GROUP_ID), 10001, 1, EARLIEST, "功能上线当晚的消息")
        mlog.insert(int(GROUP_ID), 10001, 2, "2026-08-20 12:00:00", "结算周内的消息")
        mlog.conn.commit()
        mlog.close()

        self.plugin = WeeklyReportPlugin(make_group_message("meta"))
        self.plugin.api = MockApiWrapper(make_group_message("meta"))
        self.db = self.plugin.dbmanager
        self.db.cur.execute("DELETE FROM weekly_reports")
        self.db.cur.execute("DELETE FROM immortal_lottery_results")
        self.db.cur.execute("DELETE FROM immortal_lottery_bets")

        # 开奖号码 6573（周日 20:00，落在本周报期内）
        self.db.cur.execute(
            "INSERT INTO immortal_lottery_results (group_id, period_key, winning_digits, bet_total, drawn_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (int(GROUP_ID), "2026-08-17", "6573", 4, "2026-08-23 20:00:00"),
        )
        self.db.cur.executemany(
            "INSERT INTO immortal_lottery_bets"
            " (group_id, period_key, user_id, digits, bet_bj_date, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            [
                (int(GROUP_ID), "2026-08-17", 301, "6573", "2026-08-17", "2026-08-17 09:00:00"),  # 4A 一等奖
                (int(GROUP_ID), "2026-08-17", 302, "6578", "2026-08-18", "2026-08-18 09:00:00"),  # 3A 二等奖
                (int(GROUP_ID), "2026-08-17", 303, "6500", "2026-08-19", "2026-08-19 09:00:00"),  # 2A 三等奖
                (int(GROUP_ID), "2026-08-17", 304, "1234", "2026-08-20", "2026-08-20 09:00:00"),  # 未中
            ],
        )
        self.db.conn.commit()

    def tearDown(self):
        self.db.cur.execute("DELETE FROM weekly_reports")
        self.db.cur.execute("DELETE FROM immortal_lottery_results")
        self.db.cur.execute("DELETE FROM immortal_lottery_bets")
        self.db.conn.commit()

    def test_immortal_winners_detail_in_report(self):
        self.plugin._generate_week("2026-08-17 08:00:00", "2026-08-24 08:00:00")
        row = self.db.weekly.get("2026-08-17", int(GROUP_ID))
        self.assertIsNotNone(row)
        data = row["data_json"]

        immortal = data["lottery"]["immortal"]
        self.assertEqual(immortal["digits"], "6573")
        self.assertEqual({w["tier"] for w in immortal["winners"]},
                         {"一等奖(4A)", "二等奖(3A)", "三等奖(2A)"})
        by_user = {w["user_id"]: w for w in immortal["winners"]}
        self.assertEqual(by_user[301]["digits"], "6573")
        self.assertEqual(by_user[302]["digits"], "6578")
        self.assertEqual(by_user[303]["digits"], "6500")
        self.assertNotIn(304, by_user)
        for w in immortal["winners"]:
            self.assertTrue(w["name"])  # 名字解析降级为 QQ 号字符串，但非空

        headline = data["headline"]
        self.assertEqual(headline["title"], "仙人彩大奖落定")
        self.assertIn("6573", headline["body"])
        stat_labels = [s["label"] for s in headline["stats"]]
        self.assertIn("大奖得主", stat_labels)

    def test_immortal_rolled_over_when_no_jackpot(self):
        # 仅一注未中：头条滚存、winners 为空列表
        self.db.cur.execute("DELETE FROM immortal_lottery_bets")
        self.db.cur.execute(
            "INSERT INTO immortal_lottery_bets"
            " (group_id, period_key, user_id, digits, bet_bj_date, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (int(GROUP_ID), "2026-08-17", 304, "1234", "2026-08-17", "2026-08-17 09:00:00"),
        )
        self.db.conn.commit()
        self.plugin._generate_week("2026-08-17 08:00:00", "2026-08-24 08:00:00")
        data = self.db.weekly.get("2026-08-17", int(GROUP_ID))["data_json"]
        self.assertEqual(data["headline"]["title"], "仙人彩奖池滚存")
        self.assertEqual(data["lottery"]["immortal"]["winners"], [])
