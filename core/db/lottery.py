from datetime import datetime, timedelta
import sqlite3


class LotteryManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cur = conn.cursor()

    def draw_count(self, user_id, stat_date):
        self.cur.execute("""
            SELECT draw_count
            FROM user_lottery_daily_stats
            WHERE stat_date = ? AND user_id = ?
        """, (stat_date, int(user_id)))
        row = self.cur.fetchone()
        return 0 if row is None else int(row[0])

    def add_draw(self, user_id, stat_date, inc=1):
        self.cur.execute("""
            INSERT INTO user_lottery_daily_stats (stat_date, user_id, draw_count)
            VALUES (?, ?, ?)
            ON CONFLICT(stat_date, user_id) DO UPDATE SET draw_count = draw_count + excluded.draw_count
        """, (stat_date, int(user_id), int(inc)))
        self.conn.commit()

    def add_spent(self, user_id, amount):
        self.cur.execute("""
            INSERT INTO user_lottery_stats (user_id, total_spent)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET total_spent = total_spent + excluded.total_spent
        """, (int(user_id), int(amount)))
        self.conn.commit()

    def spent(self, user_id):
        self.cur.execute("""
            SELECT total_spent
            FROM user_lottery_stats
            WHERE user_id = ?
        """, (int(user_id),))
        row = self.cur.fetchone()
        return 0 if row is None else int(row[0])

    def profile(self, user_id):
        self.cur.execute("""
            SELECT draw_count, duplicate_count, zero_streak, max_zero_streak, has_hit_ten, total_zeros
            FROM user_lottery_profile
            WHERE user_id = ?
        """, (int(user_id),))
        row = self.cur.fetchone()
        if not row:
            return {
                "draw_count": 0,
                "duplicate_count": 0,
                "zero_streak": 0,
                "max_zero_streak": 0,
                "has_hit_ten": 0,
                "total_zeros": 0,
            }
        return {
            "draw_count": int(row[0]),
            "duplicate_count": int(row[1]),
            "zero_streak": int(row[2]),
            "max_zero_streak": int(row[3]),
            "has_hit_ten": int(row[4]),
            "total_zeros": int(row[5]),
        }

    def upsert_profile(self, user_id, draw_count, duplicate_count, zero_streak, max_zero_streak, has_hit_ten, total_zeros):
        self.cur.execute("""
            INSERT INTO user_lottery_profile (user_id, draw_count, duplicate_count, zero_streak, max_zero_streak, has_hit_ten, total_zeros)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                draw_count = excluded.draw_count,
                duplicate_count = excluded.duplicate_count,
                zero_streak = excluded.zero_streak,
                max_zero_streak = excluded.max_zero_streak,
                has_hit_ten = excluded.has_hit_ten,
                total_zeros = excluded.total_zeros
        """, (
            int(user_id),
            int(draw_count),
            int(duplicate_count),
            int(zero_streak),
            int(max_zero_streak),
            int(has_hit_ten),
            int(total_zeros),
        ))
        self.conn.commit()

    def weekly_draw_count(self, user_id, week_start_str):
        ws = datetime.strptime(week_start_str, "%Y-%m-%d %H:%M:%S")
        we = ws + timedelta(days=7)
        self.cur.execute("""
            SELECT COALESCE(SUM(draw_count), 0)
            FROM user_lottery_daily_stats
            WHERE user_id = ? AND stat_date >= ? AND stat_date < ?
        """, (int(user_id), ws.strftime("%Y-%m-%d"), we.strftime("%Y-%m-%d")))
        row = self.cur.fetchone()
        return 0 if row is None else int(row[0])
