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
        """keyset 分页：按 (received_at DESC, id DESC)。cursor=(received_at, id) 或 None。
        首列 rowid 为单调插入序（未读边界），事件 id 为随机 uuid，不可替代 rowid。"""
        cols = (
            "rowid, id, source, received_at, actor_id, actor_qq, target_type, target_url,"
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

    # —— 每用户未读状态（rowid 单调边界 + 逐事件已读回执）——
    # 未读判定统一为：事件 rowid > 边界，且 (user_id, event_id) 无回执。
    # 不得用 (received_at, id) 组合做新旧比较：received_at 秒级精度、id 为随机 uuid。

    def get_or_init_watermark(self, user_id: str) -> int:
        """返回该用户水印 position（rowid 边界；空时间线为 0）。首次访问惰性初始化：
        以当前 MAX(rowid) 为基线，即「首访已有历史视为已读」。"""
        self.cur.execute(
            "SELECT position FROM timeline_user_watermarks WHERE user_id = ?", (user_id,)
        )
        row = self.cur.fetchone()
        if row:
            return int(row[0])
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.cur.execute(
                "SELECT position FROM timeline_user_watermarks WHERE user_id = ?",
                (user_id,),
            )
            row = self.cur.fetchone()
            if row:
                self.conn.commit()
                return int(row[0])
            self.cur.execute("SELECT MAX(rowid) FROM timeline_events")
            max_row = self.cur.fetchone()
            position = int(max_row[0]) if max_row and max_row[0] is not None else 0
            self.cur.execute(
                "INSERT OR IGNORE INTO timeline_user_watermarks (user_id, position)"
                " VALUES (?, ?)",
                (user_id, position),
            )
            self.conn.commit()
            return position
        except Exception:
            self.conn.rollback()
            raise

    def read_event_ids(self, user_id: str, event_ids: list[str]) -> set[str]:
        """批量查询该用户已读回执中的事件 id 集合。"""
        if not event_ids:
            return set()
        q = ",".join("?" for _ in event_ids)
        self.cur.execute(
            f"SELECT event_id FROM timeline_read_events"
            f" WHERE user_id = ? AND event_id IN ({q})",
            [user_id, *event_ids],
        )
        return {r[0] for r in self.cur.fetchall()}

    def count_unread_after(self, user_id: str, lower_rowid: int) -> int:
        """统计 rowid > lower_rowid 且该用户无回执的事件数（轮询轻量计数）。"""
        self.cur.execute(
            """
            SELECT COUNT(*) FROM timeline_events e
            WHERE e.rowid > ?
              AND e.id NOT IN (
                  SELECT event_id FROM timeline_read_events WHERE user_id = ?
              )
            """,
            (lower_rowid, user_id),
        )
        row = self.cur.fetchone()
        return int(row[0]) if row else 0

    def page_unread_after(self, user_id: str, lower_rowid: int, limit: int) -> list[tuple]:
        """按 rowid ASC 取 rowid > lower_rowid 且无回执的事件（最老一批，接口侧再倒序）。"""
        cols = (
            "rowid, id, source, received_at, actor_id, actor_qq, target_type, target_url,"
            " title, description, data, dedup_key"
        )
        self.cur.execute(
            f"""
            SELECT {cols} FROM timeline_events e
            WHERE e.rowid > ?
              AND e.id NOT IN (
                  SELECT event_id FROM timeline_read_events WHERE user_id = ?
              )
            ORDER BY e.rowid ASC LIMIT ?
            """,
            (lower_rowid, user_id, limit),
        )
        return self.cur.fetchall()

    def mark_read_events(self, user_id: str, event_ids: list[str]) -> int:
        """上报已读回执，返回该用户剩余未读事件数。同一事务内：
        仅对仍存在的事件写回执（FK 安全）；剩余数为 0 时把水印推进到
        max(现有 position, 当前 MAX(rowid))（max 夹紧防撤回导致回退），
        并删除 rowid <= 新水印 的回执。重复/乱序/跨标签页提交均不得让状态回退。"""
        self.get_or_init_watermark(user_id)
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            uniq = list(dict.fromkeys(event_ids or []))
            if uniq:
                q = ",".join("?" for _ in uniq)
                self.cur.execute(
                    f"INSERT OR IGNORE INTO timeline_read_events (user_id, event_id)"
                    f" SELECT ?, id FROM timeline_events WHERE id IN ({q})",
                    [user_id, *uniq],
                )
            self.cur.execute(
                "SELECT position FROM timeline_user_watermarks WHERE user_id = ?",
                (user_id,),
            )
            row = self.cur.fetchone()
            position = int(row[0]) if row else 0
            self.cur.execute(
                """
                SELECT COUNT(*) FROM timeline_events e
                WHERE e.rowid > ?
                  AND e.id NOT IN (
                      SELECT event_id FROM timeline_read_events WHERE user_id = ?
                  )
                """,
                (position, user_id),
            )
            remaining = int(self.cur.fetchone()[0])
            if remaining == 0:
                self.cur.execute("SELECT MAX(rowid) FROM timeline_events")
                max_row = self.cur.fetchone()
                cur_max = int(max_row[0]) if max_row and max_row[0] is not None else 0
                new_pos = max(position, cur_max)
                self.cur.execute(
                    "UPDATE timeline_user_watermarks SET position = ? WHERE user_id = ?",
                    (new_pos, user_id),
                )
                if new_pos > 0:
                    self.cur.execute(
                        "DELETE FROM timeline_read_events"
                        " WHERE user_id = ? AND event_id IN ("
                        "   SELECT id FROM timeline_events WHERE rowid <= ?)",
                        (user_id, new_pos),
                    )
            self.conn.commit()
            return remaining
        except Exception:
            self.conn.rollback()
            raise
