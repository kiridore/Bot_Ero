"""群聊话题 SQLite 持久化。"""

from __future__ import annotations

import sqlite3

from core.group_topic_segmenter import TopicRecord, TopicSegmenterStore, blob_to_normalized_centroid


class GroupTopicStoreSqlite:
    """与 `DbManager` 共用同一连接。"""

    def __init__(self, conn: sqlite3.Connection, cur: sqlite3.Cursor) -> None:
        self._conn = conn
        self._cur = cur

    def list_topics(self, group_id: int) -> list[TopicRecord]:
        self._cur.execute(
            """
            SELECT id, group_id, centroid, message_count, anchor_preview
            FROM group_chat_topics
            WHERE group_id = ?
            ORDER BY id ASC
            """,
            (int(group_id),),
        )
        out: list[TopicRecord] = []
        for rid, gid, blob, mc, ap in self._cur.fetchall():
            if not isinstance(blob, (bytes, memoryview)):
                continue
            b = bytes(blob)
            out.append(
                TopicRecord(
                    id=int(rid),
                    group_id=int(gid),
                    centroid=blob_to_normalized_centroid(b),
                    message_count=int(mc),
                    anchor_preview=str(ap or ""),
                )
            )
        return out

    def insert_topic(
        self,
        group_id: int,
        centroid_blob: bytes,
        message_count: int,
        anchor_preview: str,
        created_at: str,
        updated_at: str,
    ) -> int:
        self._cur.execute(
            """
            INSERT INTO group_chat_topics (
                group_id, centroid, message_count, created_at, updated_at, anchor_preview
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                int(group_id),
                centroid_blob,
                int(message_count),
                created_at,
                updated_at,
                anchor_preview,
            ),
        )
        self._conn.commit()
        return int(self._cur.lastrowid)

    def update_topic_centroid(
        self,
        topic_id: int,
        centroid_blob: bytes,
        message_count: int,
        anchor_preview: str,
        updated_at: str,
    ) -> None:
        self._cur.execute(
            """
            UPDATE group_chat_topics
            SET centroid = ?, message_count = ?, anchor_preview = ?, updated_at = ?
            WHERE id = ?
            """,
            (centroid_blob, int(message_count), anchor_preview, updated_at, int(topic_id)),
        )
        self._conn.commit()

    def insert_message_assignment(
        self,
        topic_id: int,
        group_id: int,
        message_id: int,
        user_id: int,
        content_preview: str,
        similarity: float | None,
        created_at: str,
    ) -> None:
        self._cur.execute(
            """
            INSERT OR IGNORE INTO group_chat_topic_messages (
                topic_id, group_id, message_id, user_id, content_preview, similarity, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(topic_id),
                int(group_id),
                int(message_id),
                int(user_id),
                content_preview,
                similarity,
                created_at,
            ),
        )
        self._conn.commit()
