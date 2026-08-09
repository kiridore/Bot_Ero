"""测试发言统计插件（message_stats）。
运行: python test/test_message_stats.py
"""
import os
import sys
import sqlite3
import unittest
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.event import Event
from core.db._base import init_schema
from core.db.message_stats import MessageStatsManager
from core.db.titles import TitlesManager
from core.db.checkin import CheckinManager
from core.db.lottery import LotteryManager
from core.db.quest import QuestManager
import plugins.message_stats as message_stats_mod
from plugins.message_stats import MessageStatsPlugin, _period_windows, _stat_date
from test.helper import MockApiWrapper, make_group_message, make_private_message

DB_PATH = "/tmp/test_message_stats.db"
GID = 296470819
UID = 123456


class _Db:
    """测试用：仅挂 message_stats / titles 及称号级联所需管理器，跳过真实 DbManager 的全局库。"""
    def __init__(self, conn):
        self.message_stats = MessageStatsManager(conn)
        self.titles = TitlesManager(conn)
        self.checkin = CheckinManager(conn)
        self.lottery = LotteryManager(conn)
        self.quest = QuestManager(conn)


def _sent_text(plugin):
    assert plugin.api.sent_messages, "无消息发送"
    return plugin.api.sent_messages[-1][1][0]["data"]["text"]


def _sent_texts(plugin):
    """拼接最后一条消息的全部文本段（解锁通知为 at + text 两段）。"""
    assert plugin.api.sent_messages, "无消息发送"
    return "".join(
        seg["data"]["text"]
        for seg in plugin.api.sent_messages[-1][1]
        if seg.get("type") == "text"
    )


class TestMessageStats(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        self.conn = sqlite3.connect(DB_PATH)
        init_schema(self.conn, self.conn.cursor())
        self.db = _Db(self.conn)

    def tearDown(self):
        self.conn.close()

    def _run(self, raw):
        plugin = MessageStatsPlugin.__new__(MessageStatsPlugin)
        plugin.bot_event = Event(raw)
        plugin.api = MockApiWrapper(raw)
        plugin.dbmanager = self.db
        return plugin

    def test_count_increments(self):
        """同一上下文 handle 两次 → 日计数与总计数各 +2。"""
        raw = make_group_message("你好", user_id=UID, group_id=GID)
        p = self._run(raw)
        p.handle()
        p.handle()
        d = _stat_date(datetime.now())
        self.assertEqual(self.db.message_stats.day_count(GID, UID, d), 2)
        self.assertEqual(self.db.message_stats.total_count(UID), 2)

    def test_range_stats(self):
        """区间聚合：3 天 4 条 → (4 条, 3 活跃天)；空用户 → (0, 0)。"""
        d = datetime.strptime(_stat_date(datetime.now()), "%Y-%m-%d")
        d1 = d.strftime("%Y-%m-%d")
        d2 = (d + timedelta(days=1)).strftime("%Y-%m-%d")
        d3 = (d + timedelta(days=2)).strftime("%Y-%m-%d")
        start = d1
        end = (d + timedelta(days=3)).strftime("%Y-%m-%d")
        self.db.message_stats.increment_day(GID, UID, d1)
        self.db.message_stats.increment_day(GID, UID, d2)
        self.db.message_stats.increment_day(GID, UID, d3)
        self.db.message_stats.increment_day(GID, UID, d3)  # 同日两条
        total, days = self.db.message_stats.range_stats(GID, UID, start, end)
        self.assertEqual(total, 4)
        self.assertEqual(days, 3)
        self.assertEqual(self.db.message_stats.range_stats(GID, 999, start, end), (0, 0))

    def test_command_reply(self):
        """/发言统计 回复五行数字与库内数据一致（指令本身也被计入今日/累计）。"""
        day, week, month, year = _period_windows(datetime.now())
        d = day[0]
        day_dt = datetime.strptime(d, "%Y-%m-%d")
        week_other = week[0] if week[0] != d else (day_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        month_other = month[0] if month[0] != d else (day_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        prev_year = (datetime.strptime(year[0], "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        for _ in range(3):
            self.db.message_stats.increment_day(GID, UID, d)
        for _ in range(2):
            self.db.message_stats.increment_day(GID, UID, week_other)
        for _ in range(5):
            self.db.message_stats.increment_day(GID, UID, month_other)
        for _ in range(7):
            self.db.message_stats.increment_day(GID, UID, prev_year)
        for _ in range(100):
            self.db.message_stats.increment_total(UID)

        p = self._run(make_group_message("/发言统计", user_id=UID, group_id=GID))
        p.handle()

        # 期望值独立用 SQL 计算（不复用插件聚合路径）
        cur = self.conn.cursor()

        def _sum(start, end):
            cur.execute(
                "SELECT COALESCE(SUM(message_count), 0), COUNT(DISTINCT stat_date) "
                "FROM group_daily_message_stats "
                "WHERE group_id = ? AND user_id = ? AND stat_date >= ? AND stat_date < ?",
                (GID, UID, start, end),
            )
            return cur.fetchone()

        day_sum, day_days = _sum(*day)
        week_sum, week_days = _sum(*week)
        month_sum, month_days = _sum(*month)
        year_sum, year_days = _sum(*year)
        cur.execute(
            "SELECT COALESCE(message_count, 0) FROM user_total_message_count WHERE user_id = ?",
            (UID,),
        )
        total = cur.fetchone()[0]
        expected = (
            f"测试用户 的发言统计（本群）\n"
            f"今日：{day_sum} 条 | 活跃 {day_days} 天\n"
            f"本周：{week_sum} 条 | 活跃 {week_days} 天\n"
            f"本月：{month_sum} 条 | 活跃 {month_days} 天\n"
            f"今年：{year_sum} 条 | 活跃 {year_days} 天\n"
            f"累计：{total} 条（全群）"
        )
        self.assertEqual(_sent_text(p), expected)
        # 去年数据只出现在累计，不污染今年行
        self.assertIn(f"今年：{year_sum} 条", expected)

    def test_title_unlock(self):
        """阈值调为 1 时一条消息即解锁称号 401 并通知。"""
        old = message_stats_mod.MESSAGE_TITLE_THRESHOLDS
        message_stats_mod.MESSAGE_TITLE_THRESHOLDS = [("day_count", 1, 401)]
        try:
            p = self._run(make_group_message("好耶", user_id=UID, group_id=GID))
            p.handle()
        finally:
            message_stats_mod.MESSAGE_TITLE_THRESHOLDS = old
        self.assertTrue(self.db.titles.has(UID, 401))
        sent = _sent_texts(p)
        self.assertIn("解锁新称号", sent)
        self.assertIn("[401] 「话痨」", sent)

    def test_skip_private(self):
        """私聊 /发言统计 提示需在群内，且不计数。"""
        p = self._run(make_private_message("/发言统计", user_id=UID))
        p.handle()
        self.assertIn("需在群内", _sent_text(p))
        self.assertEqual(self.db.message_stats.total_count(UID), 0)


if __name__ == "__main__":
    unittest.main()
