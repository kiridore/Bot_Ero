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
from core.db.guestbook import GuestbookManager
from core.db.message_stats import MessageStatsManager


class DbManager:
    def __init__(self):
        from core.config import DB_PATH

        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
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
        self.guestbook = GuestbookManager(self.conn)
        self.message_stats = MessageStatsManager(self.conn)

    def __del__(self):
        self.conn.commit()
        self.conn.close()
