import sqlite3


class PointsManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cur = conn.cursor()

    def get(self, user_id) -> int:
        self.cur.execute("""
            SELECT points FROM user_assets
            WHERE user_id = ?
        """, (user_id, ))
        row = self.cur.fetchone()
        if row:
            return row[0]
        else:
            self.cur.execute("""
                INSERT INTO user_assets (user_id, points)
                VALUES (?, 0)
            """, (user_id, ))
            return 0

    def set(self, user_id, value):
        self.cur.execute("""
            INSERT INTO user_assets (user_id, points)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET points=excluded.points
        """, (user_id, value))
        self.conn.commit()

    def adjust(self, user_id, delta: int, commit: bool = True):
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

    def leaderboard(self, limit=10):
        self.cur.execute("""
            SELECT user_id, points
            FROM user_assets
            ORDER BY points DESC, CAST(user_id AS INTEGER) ASC
            LIMIT ?
        """, (limit,))
        return self.cur.fetchall()

    def grant_all(self, amount):
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
