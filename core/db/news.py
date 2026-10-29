from datetime import datetime
import sqlite3


class NewsManager:
    """新闻订阅与推送去重游标。"""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cur = conn.cursor()

    def subscribe(self, user_id: int, source_id: str) -> None:
        self.cur.execute(
            "INSERT OR IGNORE INTO news_subscriptions (user_id, source_id, subscribed_at) VALUES (?, ?, ?)",
            (int(user_id), source_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        self.conn.commit()

    def unsubscribe(self, user_id: int, source_id: str) -> int:
        """删除订阅，返回删除行数（0 = 本来未订阅）。"""
        self.cur.execute(
            "DELETE FROM news_subscriptions WHERE user_id = ? AND source_id = ?",
            (int(user_id), source_id),
        )
        self.conn.commit()
        return self.cur.rowcount

    def is_subscribed(self, user_id: int, source_id: str) -> bool:
        self.cur.execute(
            "SELECT 1 FROM news_subscriptions WHERE user_id = ? AND source_id = ?",
            (int(user_id), source_id),
        )
        return self.cur.fetchone() is not None

    def subscribers(self, source_id: str) -> list[int]:
        self.cur.execute(
            "SELECT user_id FROM news_subscriptions WHERE source_id = ? ORDER BY user_id",
            (source_id,),
        )
        return [int(row[0]) for row in self.cur.fetchall()]

    def get_cursor(self, source_id: str) -> str | None:
        self.cur.execute(
            "SELECT cursor FROM news_push_state WHERE source_id = ?",
            (source_id,),
        )
        row = self.cur.fetchone()
        return None if row is None else str(row[0])

    def save_cursor(self, source_id: str, cursor: str) -> None:
        self.cur.execute(
            """INSERT INTO news_push_state (source_id, cursor, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(source_id) DO UPDATE SET cursor = excluded.cursor, updated_at = excluded.updated_at""",
            (source_id, str(cursor), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        self.conn.commit()
