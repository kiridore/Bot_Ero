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
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS user_lottery_daily_stats (
                stat_date TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                draw_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (stat_date, user_id)
            );
        """)
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS user_remedy_usage (
                year INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                used_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (year, user_id)
            );
        """)
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS user_lottery_stats (
                user_id INTEGER PRIMARY KEY,
                total_spent INTEGER NOT NULL DEFAULT 0
            );
        """)
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS user_weekly_streak_reward_claims (
                user_id INTEGER NOT NULL,
                week_start TEXT NOT NULL,
                claimed_at TEXT NOT NULL,
                PRIMARY KEY (user_id, week_start)
            );
        """)
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS user_attendance_reward_claims (
                user_id INTEGER NOT NULL,
                reward_type TEXT NOT NULL,
                period_key TEXT NOT NULL,
                points INTEGER NOT NULL,
                claimed_at TEXT NOT NULL,
                PRIMARY KEY (user_id, reward_type, period_key)
            );
        """)
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS user_lottery_profile (
                user_id INTEGER PRIMARY KEY,
                draw_count INTEGER NOT NULL DEFAULT 0,
                duplicate_count INTEGER NOT NULL DEFAULT 0,
                zero_streak INTEGER NOT NULL DEFAULT 0,
                max_zero_streak INTEGER NOT NULL DEFAULT 0,
                has_hit_ten INTEGER NOT NULL DEFAULT 0
            );
        """)
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS shop_stock (
                product_id TEXT PRIMARY KEY,
                stock INTEGER NOT NULL
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
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS group_alarms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                creator_user_id INTEGER NOT NULL,
                fire_at TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                fired INTEGER NOT NULL DEFAULT 0,
                is_private INTEGER NOT NULL DEFAULT 0,
                is_recurring INTEGER NOT NULL DEFAULT 0,
                repeat_y INTEGER NOT NULL DEFAULT 0,
                repeat_m INTEGER NOT NULL DEFAULT 0,
                repeat_d INTEGER NOT NULL DEFAULT 0,
                recur_kind INTEGER NOT NULL DEFAULT 0,
                recur_a INTEGER NOT NULL DEFAULT 0,
                recur_b INTEGER NOT NULL DEFAULT 0,
                recur_c INTEGER NOT NULL DEFAULT 0
            );
        """)
        self.cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_group_alarms_due ON group_alarms (fired, fire_at)"
        )
        self.cur.execute("PRAGMA table_info(group_alarms)")
        _alarm_cols = [row[1] for row in self.cur.fetchall()]
        if _alarm_cols and "is_private" not in _alarm_cols:
            self.cur.execute(
                "ALTER TABLE group_alarms ADD COLUMN is_private INTEGER NOT NULL DEFAULT 0"
            )
        self.cur.execute("PRAGMA table_info(group_alarms)")
        _alarm_cols2 = [row[1] for row in self.cur.fetchall()]
        for col, ddl in (
            ("is_recurring", "ALTER TABLE group_alarms ADD COLUMN is_recurring INTEGER NOT NULL DEFAULT 0"),
            ("repeat_y", "ALTER TABLE group_alarms ADD COLUMN repeat_y INTEGER NOT NULL DEFAULT 0"),
            ("repeat_m", "ALTER TABLE group_alarms ADD COLUMN repeat_m INTEGER NOT NULL DEFAULT 0"),
            ("repeat_d", "ALTER TABLE group_alarms ADD COLUMN repeat_d INTEGER NOT NULL DEFAULT 0"),
            ("recur_kind", "ALTER TABLE group_alarms ADD COLUMN recur_kind INTEGER NOT NULL DEFAULT 0"),
            ("recur_a", "ALTER TABLE group_alarms ADD COLUMN recur_a INTEGER NOT NULL DEFAULT 0"),
            ("recur_b", "ALTER TABLE group_alarms ADD COLUMN recur_b INTEGER NOT NULL DEFAULT 0"),
            ("recur_c", "ALTER TABLE group_alarms ADD COLUMN recur_c INTEGER NOT NULL DEFAULT 0"),
        ):
            if _alarm_cols2 and col not in _alarm_cols2:
                self.cur.execute(ddl)
                self.cur.execute("PRAGMA table_info(group_alarms)")
                _alarm_cols2 = [row[1] for row in self.cur.fetchall()]
        # 旧版「每N日」循环：repeat_* 纯日间隔 → recur_kind=1；含年/月的旧循环不再支持，改为一次性
        self.cur.execute(
            """
            UPDATE group_alarms
            SET recur_kind = 1, recur_a = repeat_d, recur_b = 0, recur_c = 0
            WHERE is_recurring = 1 AND recur_kind = 0
              AND repeat_y = 0 AND repeat_m = 0 AND repeat_d > 0
            """
        )
        self.cur.execute(
            """
            UPDATE group_alarms
            SET is_recurring = 0, recur_kind = 0, recur_a = 0, recur_b = 0, recur_c = 0
            WHERE is_recurring = 1 AND recur_kind = 0
              AND NOT (repeat_y = 0 AND repeat_m = 0 AND repeat_d > 0)
            """
        )
        self.conn.commit()

    def __del__(self):
        self.conn.commit()
        self.conn.close()

    def add_group_alarm(
        self,
        creator_user_id: int,
        fire_at: datetime,
        content: str,
        group_id: int | None = None,
        is_private: bool = False,
        recur: tuple[int, int, int, int] | None = None,
    ) -> int:
        fs = fire_at.strftime("%Y-%m-%d %H:%M:%S")
        cs = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        gid = 0 if is_private or group_id is None else int(group_id)
        priv = 1 if is_private else 0
        if recur:
            k, a, b, c = int(recur[0]), int(recur[1]), int(recur[2]), int(recur[3])
            rec = 1
        else:
            k = a = b = c = 0
            rec = 0
        ry = rm = rd = 0
        self.cur.execute(
            """
            INSERT INTO group_alarms (
                group_id, creator_user_id, fire_at, content, created_at, fired, is_private,
                is_recurring, repeat_y, repeat_m, repeat_d,
                recur_kind, recur_a, recur_b, recur_c
            )
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (gid, int(creator_user_id), fs, content, cs, priv, rec, ry, rm, rd, k, a, b, c),
        )
        self.conn.commit()
        return int(self.cur.lastrowid)

    def list_pending_alarms_for_user(self, creator_user_id: int, group_id: int | None = None):
        if group_id is None:
            self.cur.execute(
                """
                SELECT id, fire_at, content, is_recurring,
                       recur_kind, recur_a, recur_b, recur_c
                FROM group_alarms
                WHERE creator_user_id = ? AND is_private = 1 AND fired = 0
                ORDER BY fire_at ASC
                """,
                (int(creator_user_id),),
            )
        else:
            self.cur.execute(
                """
                SELECT id, fire_at, content, is_recurring,
                       recur_kind, recur_a, recur_b, recur_c
                FROM group_alarms
                WHERE creator_user_id = ? AND group_id = ? AND is_private = 0 AND fired = 0
                ORDER BY fire_at ASC
                """,
                (int(creator_user_id), int(group_id)),
            )
        return self.cur.fetchall()

    def cancel_group_alarm(
        self, alarm_id: int, creator_user_id: int, group_id: int | None = None
    ) -> bool:
        if group_id is None:
            self.cur.execute(
                """
                DELETE FROM group_alarms
                WHERE id = ? AND creator_user_id = ? AND is_private = 1 AND fired = 0
                """,
                (int(alarm_id), int(creator_user_id)),
            )
        else:
            self.cur.execute(
                """
                DELETE FROM group_alarms
                WHERE id = ? AND group_id = ? AND creator_user_id = ? AND is_private = 0 AND fired = 0
                """,
                (int(alarm_id), int(group_id), int(creator_user_id)),
            )
        self.conn.commit()
        return self.cur.rowcount > 0

    def get_due_alarms(self, now: datetime, limit: int = 200):
        ns = now.strftime("%Y-%m-%d %H:%M:%S")
        self.cur.execute(
            """
            SELECT id, group_id, creator_user_id, content, fire_at, is_private,
                   is_recurring, recur_kind, recur_a, recur_b, recur_c
            FROM group_alarms
            WHERE fired = 0 AND fire_at <= ?
            ORDER BY fire_at ASC
            LIMIT ?
            """,
            (ns, int(limit)),
        )
        return self.cur.fetchall()

    def try_mark_alarm_fired(self, alarm_id: int) -> bool:
        self.cur.execute(
            "UPDATE group_alarms SET fired = 1 WHERE id = ? AND fired = 0 AND is_recurring = 0",
            (int(alarm_id),),
        )
        self.conn.commit()
        return self.cur.rowcount > 0

    def try_advance_recurring_fire_at(
        self, alarm_id: int, prev_fire_at: str, next_fire_at: datetime
    ) -> bool:
        nxt = next_fire_at.strftime("%Y-%m-%d %H:%M:%S")
        self.cur.execute(
            """
            UPDATE group_alarms
            SET fire_at = ?
            WHERE id = ? AND is_recurring = 1 AND fired = 0 AND fire_at = ?
            """,
            (nxt, int(alarm_id), prev_fire_at),
        )
        self.conn.commit()
        return self.cur.rowcount > 0

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

    def adjust_user_points(self, user_id, delta: int, commit: bool = True):
        user_id = str(user_id)
        delta = int(delta)
        self.cur.execute("""
            INSERT OR IGNORE INTO user_assets (user_id, points)
            VALUES (?, 0)
        """, (user_id,))
        self.cur.execute("""
            UPDATE user_assets SET points = points + ?
            WHERE user_id = ?
        """, (delta, user_id))
        if commit:
            self.conn.commit()

    def ensure_shop_stock(self, product_id: str, default_stock: int):
        self.cur.execute("""
            INSERT OR IGNORE INTO shop_stock (product_id, stock)
            VALUES (?, ?)
        """, (str(product_id), int(default_stock)))
        self.conn.commit()

    def get_shop_stock(self, product_id: str):
        self.cur.execute("""
            SELECT stock FROM shop_stock WHERE product_id = ?
        """, (str(product_id),))
        row = self.cur.fetchone()
        return None if row is None else int(row[0])

    def redeem_shop_item(self, product_id: str, user_id, cost: int, grant_fn) -> tuple:
        """原子兑换：扣积分与库存（stock=-1 为不限量）、执行 grant_fn；任一步失败则整笔回滚。"""
        product_id = str(product_id)
        user_id_s = str(user_id)
        cost = int(cost)
        self.cur.execute("BEGIN IMMEDIATE")
        try:
            self.cur.execute(
                "INSERT OR IGNORE INTO user_assets (user_id, points) VALUES (?, 0)",
                (user_id_s,),
            )
            self.cur.execute("SELECT points FROM user_assets WHERE user_id = ?", (user_id_s,))
            row = self.cur.fetchone()
            points = 0 if row is None or row[0] is None else int(row[0])
            if points < cost:
                self.conn.rollback()
                return False, "积分不足"

            self.cur.execute("SELECT stock FROM shop_stock WHERE product_id = ?", (product_id,))
            srow = self.cur.fetchone()
            if srow is None:
                self.conn.rollback()
                return False, "商品不存在"
            stock = int(srow[0])
            if stock == 0:
                self.conn.rollback()
                return False, "库存不足"
            if stock > 0:
                self.cur.execute(
                    "UPDATE shop_stock SET stock = stock - 1 WHERE product_id = ? AND stock > 0",
                    (product_id,),
                )
                if self.cur.rowcount == 0:
                    self.conn.rollback()
                    return False, "库存不足"
            elif stock != -1:
                self.conn.rollback()
                return False, "库存数据异常"

            self.cur.execute(
                "UPDATE user_assets SET points = points - ? WHERE user_id = ? AND points >= ?",
                (cost, user_id_s, cost),
            )
            if self.cur.rowcount == 0:
                self.conn.rollback()
                return False, "积分不足"
            try:
                grant_fn()
            except Exception as e:
                self.conn.rollback()
                return False, str(e) or "发放失败"
            self.conn.commit()
            return True, "ok"
        except Exception as e:
            self.conn.rollback()
            return False, str(e) or "兑换失败"

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

    def unlock_title(self, user_id, title_id, commit: bool = True):
        self.cur.execute("""
            INSERT OR IGNORE INTO user_titles (user_id, title_id, unlocked_at)
            VALUES (?, ?, ?)
        """, (str(user_id), int(title_id), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        inserted = self.cur.rowcount > 0
        if commit:
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

    def get_lottery_draw_count(self, user_id, stat_date):
        self.cur.execute("""
            SELECT draw_count
            FROM user_lottery_daily_stats
            WHERE stat_date = ? AND user_id = ?
        """, (stat_date, int(user_id)))
        row = self.cur.fetchone()
        return 0 if row is None else int(row[0])

    def add_lottery_draw_count(self, user_id, stat_date, inc=1):
        self.cur.execute("""
            INSERT INTO user_lottery_daily_stats (stat_date, user_id, draw_count)
            VALUES (?, ?, ?)
            ON CONFLICT(stat_date, user_id) DO UPDATE SET draw_count = draw_count + excluded.draw_count
        """, (stat_date, int(user_id), int(inc)))
        self.conn.commit()

    def has_checkin_on_date(self, user_id, date_str):
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

    def get_user_remedy_used(self, year, user_id):
        self.cur.execute("""
            SELECT used_count
            FROM user_remedy_usage
            WHERE year = ? AND user_id = ?
        """, (int(year), int(user_id)))
        row = self.cur.fetchone()
        return 0 if row is None else int(row[0])

    def add_user_remedy_used(self, year, user_id, inc=1):
        self.cur.execute("""
            INSERT INTO user_remedy_usage (year, user_id, used_count)
            VALUES (?, ?, ?)
            ON CONFLICT(year, user_id) DO UPDATE SET used_count = used_count + excluded.used_count
        """, (int(year), int(user_id), int(inc)))
        self.conn.commit()

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

    def add_lottery_spent(self, user_id, amount):
        self.cur.execute("""
            INSERT INTO user_lottery_stats (user_id, total_spent)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET total_spent = total_spent + excluded.total_spent
        """, (int(user_id), int(amount)))
        self.conn.commit()

    def get_lottery_spent(self, user_id):
        self.cur.execute("""
            SELECT total_spent
            FROM user_lottery_stats
            WHERE user_id = ?
        """, (int(user_id),))
        row = self.cur.fetchone()
        return 0 if row is None else int(row[0])

    def claim_weekly_streak_reward(self, user_id, week_start):
        self.cur.execute("""
            INSERT OR IGNORE INTO user_weekly_streak_reward_claims (user_id, week_start, claimed_at)
            VALUES (?, ?, ?)
        """, (int(user_id), str(week_start), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        ok = self.cur.rowcount > 0
        self.conn.commit()
        return ok

    def get_distinct_checkin_day_count(self, user_id, start_datetime_str, end_datetime_str):
        self.cur.execute("""
            SELECT COUNT(DISTINCT substr(checkin_date, 1, 10))
            FROM checkin_records
            WHERE user_id = ?
            AND checkin_date >= ?
            AND checkin_date < ?
        """, (int(user_id), start_datetime_str, end_datetime_str))
        row = self.cur.fetchone()
        return 0 if row is None or row[0] is None else int(row[0])

    def claim_attendance_reward(self, user_id, reward_type, period_key, points):
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

    def revoke_attendance_reward_if_claimed(self, user_id, reward_type, period_key):
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

    def revoke_attendance_rewards_by_type_and_prefix(self, user_id, reward_type, period_prefix):
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

    def revoke_attendance_rewards_by_type_and_range(self, user_id, reward_type, start_key, end_key):
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

    def get_total_distinct_checkin_days(self, user_id):
        self.cur.execute("""
            SELECT COUNT(DISTINCT substr(checkin_date, 1, 10))
            FROM checkin_records
            WHERE user_id = ?
        """, (int(user_id),))
        row = self.cur.fetchone()
        return 0 if row is None or row[0] is None else int(row[0])

    def get_user_lottery_profile(self, user_id):
        self.cur.execute("""
            SELECT draw_count, duplicate_count, zero_streak, max_zero_streak, has_hit_ten
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
            }
        return {
            "draw_count": int(row[0]),
            "duplicate_count": int(row[1]),
            "zero_streak": int(row[2]),
            "max_zero_streak": int(row[3]),
            "has_hit_ten": int(row[4]),
        }

    def upsert_user_lottery_profile(self, user_id, draw_count, duplicate_count, zero_streak, max_zero_streak, has_hit_ten):
        self.cur.execute("""
            INSERT INTO user_lottery_profile (user_id, draw_count, duplicate_count, zero_streak, max_zero_streak, has_hit_ten)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                draw_count = excluded.draw_count,
                duplicate_count = excluded.duplicate_count,
                zero_streak = excluded.zero_streak,
                max_zero_streak = excluded.max_zero_streak,
                has_hit_ten = excluded.has_hit_ten
        """, (
            int(user_id),
            int(draw_count),
            int(duplicate_count),
            int(zero_streak),
            int(max_zero_streak),
            int(has_hit_ten),
        ))
        self.conn.commit()

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
