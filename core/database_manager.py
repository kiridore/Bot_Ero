from datetime import datetime, timedelta
import sqlite3

class DbManager:
    def __init__(self):
        self.conn = sqlite3.connect("data.db")
        self.cur = self.conn.cursor()
        self.cur.execute("""
        CREATE TABLE IF NOT EXISTS checkin_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            checkin_date TEXT NOT NULL,
            content TEXT NOT NULL
        );
        """)

        self.cur.execute('''
            CREATE TABLE IF NOT EXISTS user_assets (
                user_id TEXT PRIMARY KEY,
                points INTEGER DEFAULT 0         -- 积分字段
            );
        ''')
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS user_titles (
                user_id TEXT NOT NULL,
                title_id INTEGER NOT NULL,
                unlocked_at TEXT NOT NULL,
                PRIMARY KEY (user_id, title_id)
            );
        """)
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS user_title_state (
                user_id TEXT PRIMARY KEY,
                equipped_title INTEGER
            );
        """)
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS user_equipped_titles (
                user_id TEXT NOT NULL,
                slot INTEGER NOT NULL,
                title_id INTEGER NOT NULL,
                PRIMARY KEY (user_id, slot),
                UNIQUE (user_id, title_id)
            );
        """)
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS group_daily_message_stats (
                stat_date TEXT NOT NULL,
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                message_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (stat_date, group_id, user_id)
            );
        """)
        self.cur.execute("PRAGMA table_info(checkin_records)")
        _cols = [row[1] for row in self.cur.fetchall()]
        if "message_id" not in _cols:
            self.cur.execute("ALTER TABLE checkin_records ADD COLUMN message_id INTEGER")
        self.cur.execute("""
            INSERT OR IGNORE INTO user_equipped_titles (user_id, slot, title_id)
            SELECT user_id, 1, equipped_title
            FROM user_title_state
            WHERE equipped_title IS NOT NULL
        """)
        self.conn.commit()

    def __del__(self):
        self.conn.commit()
        self.conn.close()

    # 获取用户现在的积分
    def get_user_point(self, user_id)->int:
        self.cur.execute("""
            SELECT points FROM user_assets
            WHERE user_id = ?
        """, (user_id, ))
        row = self.cur.fetchone()
        if row:
            return row[0]
        else:
            # 同时创建一份当前用户信息
            self.cur.execute("""
                INSERT INTO user_assets (user_id, points)
                VALUES (?, 0)
            """, (user_id, ))
            return 0

    # 将用户积分设置为value值
    def set_user_point(self, user_id, value):
        self.cur.execute("""
            INSERT INTO user_assets (user_id, points)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET points=excluded.points
        """, (user_id, value))
        self.conn.commit()

    def get_point_leaderboard(self, limit=10):
        self.cur.execute("""
            SELECT user_id, points
            FROM user_assets
            ORDER BY points DESC, CAST(user_id AS INTEGER) ASC
            LIMIT ?
        """, (limit,))
        return self.cur.fetchall()

    def get_user_titles(self, user_id):
        self.cur.execute("""
            SELECT title_id
            FROM user_titles
            WHERE user_id = ?
            ORDER BY title_id ASC
        """, (str(user_id),))
        return [row[0] for row in self.cur.fetchall()]

    def unlock_title(self, user_id, title_id):
        self.cur.execute("""
            INSERT OR IGNORE INTO user_titles (user_id, title_id, unlocked_at)
            VALUES (?, ?, ?)
        """, (str(user_id), int(title_id), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        inserted = self.cur.rowcount > 0
        self.conn.commit()
        return inserted

    def has_title(self, user_id, title_id):
        self.cur.execute("""
            SELECT 1
            FROM user_titles
            WHERE user_id = ? AND title_id = ?
            LIMIT 1
        """, (str(user_id), int(title_id)))
        return self.cur.fetchone() is not None

    def get_equipped_title(self, user_id):
        titles = self.get_equipped_titles(user_id)
        if len(titles) == 0:
            return None
        return titles[0]

    def get_equipped_titles(self, user_id):
        self.cur.execute("""
            SELECT title_id
            FROM user_equipped_titles
            WHERE user_id = ?
            ORDER BY slot ASC
        """, (str(user_id),))
        return [row[0] for row in self.cur.fetchall()]

    def equip_title(self, user_id, title_id, max_count=3):
        user_id = str(user_id)
        title_id = int(title_id)
        equipped = self.get_equipped_titles(user_id)
        if title_id in equipped:
            return False, "already"
        if len(equipped) >= max_count:
            return False, "full"

        used_slots = set()
        self.cur.execute("""
            SELECT slot
            FROM user_equipped_titles
            WHERE user_id = ?
        """, (user_id,))
        for row in self.cur.fetchall():
            used_slots.add(int(row[0]))

        slot = 1
        while slot in used_slots:
            slot += 1

        self.cur.execute("""
            INSERT INTO user_equipped_titles (user_id, slot, title_id)
            VALUES (?, ?, ?)
        """, (user_id, slot, title_id))
        self.conn.commit()
        return True, "ok"

    def clear_equipped_titles(self, user_id):
        self.cur.execute("""
            DELETE FROM user_equipped_titles
            WHERE user_id = ?
        """, (str(user_id),))
        self.conn.commit()

    def set_equipped_title(self, user_id, title_id):
        # 兼容旧接口：设置为单称号装备
        user_id = str(user_id)
        self.clear_equipped_titles(user_id)
        if title_id is not None:
            self.equip_title(user_id, int(title_id), max_count=3)

    def increment_group_daily_message_count(self, stat_date, group_id, user_id, inc=1):
        self.cur.execute("""
            INSERT INTO group_daily_message_stats (stat_date, group_id, user_id, message_count)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(stat_date, group_id, user_id)
            DO UPDATE SET message_count = message_count + excluded.message_count
        """, (stat_date, int(group_id), int(user_id), int(inc)))
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

    def grant_points_to_all_users(self, amount):
        amount = int(amount)
        self.cur.execute("""
            SELECT DISTINCT user_id FROM user_assets
            UNION
            SELECT DISTINCT CAST(user_id AS TEXT) FROM checkin_records
            UNION
            SELECT DISTINCT CAST(user_id AS TEXT) FROM user_titles
            UNION
            SELECT DISTINCT user_id FROM user_title_state
            UNION
            SELECT DISTINCT user_id FROM user_equipped_titles
            UNION
            SELECT DISTINCT CAST(user_id AS TEXT) FROM group_daily_message_stats
        """)
        user_ids = [row[0] for row in self.cur.fetchall() if row[0] is not None]

        for uid in user_ids:
            self.cur.execute("""
                INSERT INTO user_assets (user_id, points)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET points = points + excluded.points
            """, (str(uid), amount))

        self.conn.commit()
        return len(user_ids)

    def insert_checkin(self, user_id, images, message_id=None):
        today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for img in images:
            self.cur.execute(
                "INSERT INTO checkin_records (user_id, checkin_date, content, message_id) VALUES (?, ?, ?, ?)",
                (user_id, today_str, img, message_id)
            )
        self.conn.commit()

    def remedy_checkin(self, user_id, day_start):
        # 从day_start开始，生成当周七天的日期填充补卡数据
        for i in range(7):
            checkin_date = (datetime.strptime(day_start, "%Y-%m-%d") + timedelta(days=i)).strftime("%Y-%m-%d 12:00:00")
            print(checkin_date)
            self.cur.execute(
                "INSERT INTO checkin_records (user_id, checkin_date, content) VALUES (?, ?, ?)",
                (user_id, checkin_date, "remedy_checkin")
            )
        self.conn.commit()

    def remedy_checkin_one_day(self, user_id, day_str):
        checkin_date = datetime.strptime(day_str, "%Y-%m-%d").strftime("%Y-%m-%d 12:00:00")
        self.cur.execute(
            "INSERT INTO checkin_records (user_id, checkin_date, content) VALUES (?, ?, ?)",
            (user_id, checkin_date, "remedy_checkin")
        )
        self.conn.commit()

    def search_checkin_year(self, user_id, year):
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

    def search_checkin_all(self, user_id, limit=9999999):
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

    def get_all_record(self, limit=9999999):
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


    def search_all_user_checkin_range(self, start_date, end_date, limit=9999999):
        self.cur.execute("""
        SELECT * FROM checkin_records
        WHERE checkin_date BETWEEN ? AND ?
        ORDER BY checkin_date DESC
        LIMIT ?
        """, (start_date, end_date, limit))
        rows = self.cur.fetchall()
        return rows

    def search_target_user_checkin_range(self, user_id, start_date, end_date, limit=9999999):
        self.cur.execute("""
        SELECT * FROM checkin_records
        WHERE user_id = ?
        AND checkin_date BETWEEN ? AND ?
        ORDER BY checkin_date DESC
        LIMIT ?
        """, (user_id, start_date, end_date, limit))
        rows = self.cur.fetchall()
        return rows

    def delete_checkin_by_id(self, target_id):
        self.cur.execute("""
            DELETE FROM checkin_records
            WHERE id = ?
        """, (target_id, ))
        self.conn.commit()

    def get_checkins_by_message_id(self, user_id, message_id):
        self.cur.execute(
            """
            SELECT * FROM checkin_records
            WHERE user_id = ? AND message_id = ?
            ORDER BY id ASC
            """,
            (user_id, message_id),
        )
        return self.cur.fetchall()

    def delete_checkin_by_message_id(self, user_id, message_id):
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

    def get_user_streaks(self, user_id):
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

        # =========================
        # 处理日期（去重）
        # =========================
        dates = sorted({
            # 添加偏移量，确保与打卡机制（八点结算）一致
            (datetime.strptime(row[0], DATE_FORMAT) - timedelta(hours = 8)).date()
            for row in rows
        })

        # =========================
        # 日 streak 统计
        # =========================
        longest_daily = 1
        current_daily = 1

        for i in range(1, len(dates)):
            if dates[i] == dates[i - 1] + timedelta(days=1):
                current_daily += 1
                longest_daily = max(longest_daily, current_daily)
            else:
                current_daily = 1

        # 当前连续日 streak（从最后一天往前推）
        today = dates[-1]
        current_daily_real = 1
        for i in range(len(dates) - 2, -1, -1):
            if dates[i] == today - timedelta(days=1):
                current_daily_real += 1
                today = dates[i]
            else:
                break

        # =========================
        # 周 streak 统计
        # =========================
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

        # 当前连续周 streak
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
