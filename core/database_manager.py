from datetime import datetime, timedelta
import sqlite3

from core.db._base import init_schema
from core.db.checkin import CheckinManager
from core.db.points import PointsManager
from core.db.shop import ShopManager
from core.db.lottery import LotteryManager
from core.db.titles import TitlesManager
from core.db.alarm import AlarmManager
from core.db.immortal import ImmortalManager
from core.db.quest import QuestManager
from core.db.activity import ActivityManager


class DbManager:
    def __init__(self):
        self.conn = sqlite3.connect("data.db")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.cur = self.conn.cursor()
        init_schema(self.conn, self.cur)

        self.checkin = CheckinManager(self.conn)
        self.points = PointsManager(self.conn)
        self.shop = ShopManager(self.conn)
        self.lottery = LotteryManager(self.conn)
        self.titles = TitlesManager(self.conn)
        self.alarm = AlarmManager(self.conn)
        self.immortal = ImmortalManager(self.conn)
        self.quest = QuestManager(self.conn)
        self.activity = ActivityManager(self.conn)

    def __del__(self):
        self.conn.commit()
        self.conn.close()

    def increment_group_daily_message_count(self, stat_date, group_id, user_id, inc=1):
        self.cur.execute("""
            INSERT INTO group_daily_message_stats (stat_date, group_id, user_id, message_count)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(stat_date, group_id, user_id)
            DO UPDATE SET message_count = message_count + excluded.message_count
        """, (stat_date, int(group_id), int(user_id), int(inc)))
        self.conn.commit()

    def increment_user_total_message_count(self, user_id, inc=1):
        self.cur.execute("""
            INSERT INTO user_total_message_count (user_id, message_count)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                message_count = message_count + excluded.message_count
        """, (int(user_id), int(inc)))
        self.conn.commit()

    def get_group_daily_message_stats(self, stat_date, group_id, limit=50):
        self.cur.execute("""
            SELECT user_id, message_count
            FROM group_daily_message_stats
            WHERE stat_date = ? AND group_id = ?
            ORDER BY message_count DESC, user_id ASC
            LIMIT ?
        """, (stat_date, int(group_id), int(limit)))
        return self.cur.fetchall()
