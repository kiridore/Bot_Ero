from datetime import datetime
import sqlite3


class AlarmManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cur = conn.cursor()

    def add(
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

    def pending(self, creator_user_id: int, group_id: int | None = None):
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

    def cancel(
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

    def due(self, now: datetime, limit: int = 200):
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

    def mark_fired(self, alarm_id: int) -> bool:
        self.cur.execute(
            "UPDATE group_alarms SET fired = 1 WHERE id = ? AND fired = 0 AND is_recurring = 0",
            (int(alarm_id),),
        )
        self.conn.commit()
        return self.cur.rowcount > 0

    def advance(
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
