"""社区时间线存储层：timeline_events 表（Event Server 只存不解析）。"""

from datetime import datetime
import sqlite3


class TimelineManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cur = conn.cursor()

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def insert(self, event_id, source, actor_id, actor_qq, target_type, target_url,
               title, description, data, dedup_key):
        """INSERT OR IGNORE：唯一约束 (source, id) 与 (source, dedup_key) 保证幂等。"""
        received_at = self._now()
        self.cur.execute(
            """
            INSERT OR IGNORE INTO timeline_events
            (id, source, received_at, actor_id, actor_qq, target_type, target_url,
             title, description, data, dedup_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (event_id, source, received_at, actor_id, actor_qq, target_type, target_url,
             title, description, data, dedup_key),
        )
        self.conn.commit()
        return self.cur.rowcount > 0

    def page(self, cursor, limit):
        """keyset 分页：按 (received_at DESC, id DESC)。cursor=(received_at, id) 或 None。"""
        cols = (
            "id, source, received_at, actor_id, actor_qq, target_type, target_url,"
            " title, description, data, dedup_key"
        )
        if cursor:
            received_at, event_id = cursor
            self.cur.execute(
                f"""
                SELECT {cols} FROM timeline_events
                WHERE received_at < ? OR (received_at = ? AND id < ?)
                ORDER BY received_at DESC, id DESC LIMIT ?
                """,
                (received_at, received_at, event_id, limit),
            )
        else:
            self.cur.execute(
                f"SELECT {cols} FROM timeline_events ORDER BY received_at DESC, id DESC LIMIT ?",
                (limit,),
            )
        return self.cur.fetchall()

    def delete_by_id(self, event_id):
        self.cur.execute("DELETE FROM timeline_events WHERE id = ?", (event_id,))
        self.conn.commit()
        return self.cur.rowcount > 0

    def delete_by_key(self, source, dedup_key):
        self.cur.execute(
            "DELETE FROM timeline_events WHERE source = ? AND dedup_key = ?",
            (source, dedup_key),
        )
        self.conn.commit()
        return self.cur.rowcount > 0
