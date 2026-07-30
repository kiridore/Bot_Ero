from datetime import datetime, timedelta
import sqlite3


class CheckinManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cur = conn.cursor()

    def insert(self, user_id, images, message_id=None):
        today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for img in images:
            self.cur.execute(
                "INSERT INTO checkin_records (user_id, checkin_date, content, message_id) VALUES (?, ?, ?, ?)",
                (user_id, today_str, img, message_id)
            )
        self.conn.commit()

    def remedy_week(self, user_id, day_start):
        for i in range(7):
            checkin_date = (datetime.strptime(day_start, "%Y-%m-%d") + timedelta(days=i)).strftime("%Y-%m-%d 12:00:00")
            print(checkin_date)
            self.cur.execute(
                "INSERT INTO checkin_records (user_id, checkin_date, content) VALUES (?, ?, ?)",
                (user_id, checkin_date, "remedy_checkin")
            )
        self.conn.commit()

    def remedy_day(self, user_id, day_str):
        checkin_date = datetime.strptime(day_str, "%Y-%m-%d").strftime("%Y-%m-%d 12:00:00")
        self.cur.execute(
            "INSERT INTO checkin_records (user_id, checkin_date, content) VALUES (?, ?, ?)",
            (user_id, checkin_date, "remedy_checkin")
        )
        self.conn.commit()

    def search_year(self, user_id, year):
        start_date = f"{year}-01-01 00:00:00"
        end_date = f"{year}-12-31 23:59:59"
        self.cur.execute(
            """
            SELECT * FROM checkin_records
            WHERE user_id = ?
            AND checkin_date BETWEEN ? AND ?
            ORDER BY checkin_date DESC
            """,
            (user_id, start_date, end_date)
        )
        rows = self.cur.fetchall()
        return rows

    def search_all(self, user_id, limit=9999999):
        self.cur.execute(
            """
            SELECT * FROM checkin_records
            WHERE user_id = ?
            ORDER BY checkin_date DESC
            LIMIT ?
            """,
            (user_id, limit)
        )
        rows = self.cur.fetchall()
        return rows

    def all_records(self, limit=9999999):
        self.cur.execute(
            """
            SELECT * FROM checkin_records
            ORDER BY checkin_date DESC
            LIMIT ?
            """,
            (limit, )
        )
        rows = self.cur.fetchall()
        return rows

    def search_range(self, start_date, end_date, limit=9999999):
        self.cur.execute("""
        SELECT * FROM checkin_records
        WHERE checkin_date BETWEEN ? AND ?
        ORDER BY checkin_date DESC
        LIMIT ?
        """, (start_date, end_date, limit))
        rows = self.cur.fetchall()
        return rows

    def search_user_range(self, user_id, start_date, end_date, limit=9999999):
        self.cur.execute("""
        SELECT * FROM checkin_records
        WHERE user_id = ?
        AND checkin_date BETWEEN ? AND ?
        ORDER BY checkin_date DESC
        LIMIT ?
        """, (user_id, start_date, end_date, limit))
        rows = self.cur.fetchall()
        return rows

    def delete(self, target_id):
        self.cur.execute("""
            DELETE FROM checkin_records
            WHERE id = ?
        """, (target_id, ))
        self.conn.commit()

    def get_by_msg(self, user_id, message_id):
        self.cur.execute(
            """
            SELECT * FROM checkin_records
            WHERE user_id = ? AND message_id = ?
            ORDER BY id ASC
            """,
            (user_id, message_id),
        )
        return self.cur.fetchall()

    def delete_by_msg(self, user_id, message_id):
        self.cur.execute(
            """
            DELETE FROM checkin_records
            WHERE user_id = ? AND message_id = ?
            """,
            (user_id, message_id),
        )
        n = self.cur.rowcount
        self.conn.commit()
        return n

    def has_on_date(self, user_id, date_str):
        start = f"{date_str} 00:00:00"
        end_dt = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
        end = end_dt.strftime("%Y-%m-%d 00:00:00")
        self.cur.execute("""
            SELECT 1
            FROM checkin_records
            WHERE user_id = ?
            AND checkin_date >= ?
            AND checkin_date < ?
            LIMIT 1
        """, (int(user_id), start, end))
        return self.cur.fetchone() is not None

    def streaks(self, user_id):
        DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
        cur = self.conn.cursor()

        cur.execute("""
            SELECT checkin_date
            FROM checkin_records
            WHERE user_id = ?
            ORDER BY checkin_date ASC
        """, (user_id,))

        rows = cur.fetchall()

        if not rows:
            return {
                "longest_daily": 0,
                "current_daily": 0,
                "longest_weekly": 0,
                "current_weekly": 0
            }

        dates = sorted({
            (datetime.strptime(row[0], DATE_FORMAT) - timedelta(hours = 8)).date()
            for row in rows
        })

        longest_daily = 1
        current_daily = 1

        for i in range(1, len(dates)):
            if dates[i] == dates[i - 1] + timedelta(days=1):
                current_daily += 1
                longest_daily = max(longest_daily, current_daily)
            else:
                current_daily = 1

        today = dates[-1]
        current_daily_real = 1
        for i in range(len(dates) - 2, -1, -1):
            if dates[i] == today - timedelta(days=1):
                current_daily_real += 1
                today = dates[i]
            else:
                break

        weeks = sorted({
            (d.isocalendar().year, d.isocalendar().week)
            for d in dates
        })

        longest_weekly = 1
        current_weekly = 1

        for i in range(1, len(weeks)):
            prev_year, prev_week = weeks[i - 1]
            curr_year, curr_week = weeks[i]

            prev_date = datetime.fromisocalendar(prev_year, prev_week, 1).date()
            next_week_date = prev_date + timedelta(weeks=1)
            next_year, next_week = next_week_date.isocalendar()[:2]

            if (curr_year, curr_week) == (next_year, next_week):
                current_weekly += 1
                longest_weekly = max(longest_weekly, current_weekly)
            else:
                current_weekly = 1

        last_year, last_week = weeks[-1]
        current_weekly_real = 1

        prev_date = datetime.fromisocalendar(last_year, last_week, 1).date()

        for i in range(len(weeks) - 2, -1, -1):
            test_date = prev_date - timedelta(weeks=1)
            expected_year, expected_week = test_date.isocalendar()[:2]

            if weeks[i] == (expected_year, expected_week):
                current_weekly_real += 1
                prev_date = test_date
            else:
                break

        return {
            "longest_daily": longest_daily,
            "current_daily": current_daily_real,
            "longest_weekly": longest_weekly,
            "current_weekly": current_weekly_real
        }

    def count_days(self, user_id, start_datetime_str, end_datetime_str):
        self.cur.execute("""
            SELECT COUNT(DISTINCT substr(datetime(checkin_date, '-8 hours'), 1, 10))
            FROM checkin_records
            WHERE user_id = ?
            AND checkin_date >= ?
            AND checkin_date < ?
        """, (int(user_id), start_datetime_str, end_datetime_str))
        row = self.cur.fetchone()
        return 0 if row is None or row[0] is None else int(row[0])

    def count_all_days(self, user_id):
        self.cur.execute("""
            SELECT COUNT(DISTINCT substr(checkin_date, 1, 10))
            FROM checkin_records
            WHERE user_id = ?
        """, (int(user_id),))
        row = self.cur.fetchone()
        return 0 if row is None or row[0] is None else int(row[0])

    def remedy_used(self, year, user_id):
        self.cur.execute("""
            SELECT used_count
            FROM user_remedy_usage
            WHERE year = ? AND user_id = ?
        """, (int(year), int(user_id)))
        row = self.cur.fetchone()
        return 0 if row is None else int(row[0])

    def add_remedy_used(self, year, user_id, inc=1):
        self.cur.execute("""
            INSERT INTO user_remedy_usage (year, user_id, used_count)
            VALUES (?, ?, ?)
            ON CONFLICT(year, user_id) DO UPDATE SET used_count = used_count + excluded.used_count
        """, (int(year), int(user_id), int(inc)))
        self.conn.commit()

    def claim_weekly(self, user_id, week_start):
        self.cur.execute("""
            INSERT OR IGNORE INTO user_weekly_streak_reward_claims (user_id, week_start, claimed_at)
            VALUES (?, ?, ?)
        """, (int(user_id), str(week_start), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        ok = self.cur.rowcount > 0
        self.conn.commit()
        return ok

    def claim_attendance(self, user_id, reward_type, period_key, points):
        self.cur.execute("""
            INSERT OR IGNORE INTO user_attendance_reward_claims (user_id, reward_type, period_key, points, claimed_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            int(user_id),
            str(reward_type),
            str(period_key),
            int(points),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ))
        ok = self.cur.rowcount > 0
        self.conn.commit()
        return ok

    def revoke_attendance(self, user_id, reward_type, period_key):
        self.cur.execute("""
            SELECT points
            FROM user_attendance_reward_claims
            WHERE user_id = ? AND reward_type = ? AND period_key = ?
            LIMIT 1
        """, (int(user_id), str(reward_type), str(period_key)))
        row = self.cur.fetchone()
        if not row:
            return 0
        points = int(row[0])
        self.cur.execute("""
            DELETE FROM user_attendance_reward_claims
            WHERE user_id = ? AND reward_type = ? AND period_key = ?
        """, (int(user_id), str(reward_type), str(period_key)))
        self.conn.commit()
        return points

    def revoke_attendance_prefix(self, user_id, reward_type, period_prefix):
        self.cur.execute("""
            SELECT COALESCE(SUM(points), 0)
            FROM user_attendance_reward_claims
            WHERE user_id = ? AND reward_type = ? AND period_key LIKE ?
        """, (int(user_id), str(reward_type), f"{period_prefix}%"))
        row = self.cur.fetchone()
        total = 0 if row is None or row[0] is None else int(row[0])
        if total <= 0:
            return 0
        self.cur.execute("""
            DELETE FROM user_attendance_reward_claims
            WHERE user_id = ? AND reward_type = ? AND period_key LIKE ?
        """, (int(user_id), str(reward_type), f"{period_prefix}%"))
        self.conn.commit()
        return total

    def revoke_attendance_range(self, user_id, reward_type, start_key, end_key):
        self.cur.execute("""
            SELECT COALESCE(SUM(points), 0)
            FROM user_attendance_reward_claims
            WHERE user_id = ?
            AND reward_type = ?
            AND period_key >= ?
            AND period_key < ?
        """, (int(user_id), str(reward_type), str(start_key), str(end_key)))
        row = self.cur.fetchone()
        total = 0 if row is None or row[0] is None else int(row[0])
        if total <= 0:
            return 0
        self.cur.execute("""
            DELETE FROM user_attendance_reward_claims
            WHERE user_id = ?
            AND reward_type = ?
            AND period_key >= ?
            AND period_key < ?
        """, (int(user_id), str(reward_type), str(start_key), str(end_key)))
        self.conn.commit()
        return total
