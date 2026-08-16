"""独立消息日志库：只记群消息，永久保留，供周报聚合使用。"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from core.config import MESSAGE_LOG_DB_PATH


class MessageLogManager:
    """管理 `server_data/message_log.db`（独立库，仿 DbManager 的 WAL + busy_timeout）。"""

    def __init__(self, db_path: str | None = None):
        from pathlib import Path

        path = Path(db_path) if db_path else Path(MESSAGE_LOG_DB_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.cur = self.conn.cursor()
        self.init_schema()

    def init_schema(self) -> None:
        self.cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            msg_id INTEGER NOT NULL,
            reply_to_msg_id INTEGER,
            sent_at TEXT NOT NULL,
            text TEXT NOT NULL DEFAULT '',
            has_image INTEGER NOT NULL DEFAULT 0,
            UNIQUE (msg_id)
        );
        """)
        self.cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_group_time "
            "ON messages (group_id, sent_at)"
        )
        self.cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_text ON messages (text)"
        )
        self.conn.commit()

    def insert(
        self,
        group_id: int,
        user_id: int,
        msg_id: int,
        sent_at: str,
        text: str,
        has_image: int = 0,
        reply_to_msg_id: int | None = None,
    ) -> bool:
        """INSERT OR IGNORE 防重。返回 True 表示实际插入。"""
        self.cur.execute(
            """
            INSERT OR IGNORE INTO messages
                (group_id, user_id, msg_id, reply_to_msg_id, sent_at, text, has_image)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (int(group_id), int(user_id), int(msg_id), reply_to_msg_id, sent_at, text, int(has_image)),
        )
        inserted = self.cur.rowcount > 0
        self.conn.commit()
        return inserted

    def get_week(self, group_id: int, start: str, end: str) -> list[dict]:
        """返回 [start, end) 周界内的群消息（按发送时间升序）。"""
        self.cur.execute(
            """
            SELECT id, group_id, user_id, msg_id, reply_to_msg_id, sent_at, text, has_image
            FROM messages
            WHERE group_id = ? AND sent_at >= ? AND sent_at < ?
            ORDER BY sent_at ASC, id ASC
            """,
            (int(group_id), start, end),
        )
        rows = self.cur.fetchall()
        keys = ("id", "group_id", "user_id", "msg_id", "reply_to_msg_id", "sent_at", "text", "has_image")
        return [dict(zip(keys, row)) for row in rows]

    def close(self) -> None:
        try:
            self.conn.commit()
            self.conn.close()
        except sqlite3.Error:
            pass
