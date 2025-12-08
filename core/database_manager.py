from datetime import datetime
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

    def insert_checkin(self, user_id, images):
        today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for img in images:
            self.cur.execute(
                "INSERT INTO checkin_records (user_id, checkin_date, content) VALUES (?, ?, ?)",
                (user_id, today_str, img)
            )
        self.conn.commit()

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
