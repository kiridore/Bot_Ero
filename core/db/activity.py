import sqlite3
from datetime import datetime


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class ActivityManager:
    def __init__(self, conn):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row  # dict(row) 依赖 Row 工厂
        self.cur = conn.cursor()

    def _rows(self, sql, params=()):
        self.cur.execute(sql, params)
        return [dict(r) for r in self.cur.fetchall()]

    def _row(self, sql, params=()):
        self.cur.execute(sql, params)
        r = self.cur.fetchone()
        return dict(r) if r else None

    # ── activities ──
    def create_activity(self, group_id, type_, title, description, created_by,
                        hours_per_user=None, deadline=None,
                        signup_deadline=None) -> int:
        self.cur.execute(
            "INSERT INTO activities (group_id, type, title, description, status, created_by,"
            " signup_deadline, deadline, hours_per_user, created_at)"
            " VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)",
            (int(group_id), type_, title, description, str(created_by),
             signup_deadline, deadline, hours_per_user, _now()),
        )
        self.conn.commit()
        return self.cur.lastrowid

    def get_activity(self, activity_id) -> dict | None:
        return self._row("SELECT * FROM activities WHERE id = ?", (int(activity_id),))

    def get_active_activity(self, group_id) -> dict | None:
        return self._row(
            "SELECT * FROM activities WHERE group_id = ? AND status IN ('open', 'running')"
            " ORDER BY id DESC LIMIT 1",
            (int(group_id),),
        )

    def get_active_activities(self) -> list[dict]:
        return self._rows(
            "SELECT * FROM activities WHERE status IN ('open', 'running')"
            " ORDER BY id ASC"
        )

    def get_running_activities(self) -> list[dict]:
        return self._rows("SELECT * FROM activities WHERE status = 'running'")

    def update_activity(self, activity_id, **fields):
        if not fields:
            return
        sets = ", ".join(f"{k} = ?" for k in fields)
        self.cur.execute(
            f"UPDATE activities SET {sets} WHERE id = ?",
            (*fields.values(), int(activity_id)),
        )
        self.conn.commit()

    # ── members ──
    def add_member(self, activity_id, user_id, nickname) -> bool:
        self.cur.execute(
            "INSERT OR IGNORE INTO activity_members (activity_id, user_id, nickname)"
            " VALUES (?, ?, ?)",
            (int(activity_id), str(user_id), nickname),
        )
        self.conn.commit()
        return self.cur.rowcount > 0

    def count_members(self, activity_id) -> int:
        self.cur.execute(
            "SELECT COUNT(*) FROM activity_members WHERE activity_id = ?", (int(activity_id),)
        )
        return self.cur.fetchone()[0]

    def get_member(self, activity_id, user_id) -> dict | None:
        return self._row(
            "SELECT * FROM activity_members WHERE activity_id = ? AND user_id = ?",
            (int(activity_id), str(user_id)),
        )

    def get_members(self, activity_id) -> list[dict]:
        return self._rows(
            "SELECT * FROM activity_members WHERE activity_id = ? ORDER BY seq ASC",
            (int(activity_id),),
        )

    def remove_member(self, activity_id, user_id):
        self.cur.execute(
            "DELETE FROM activity_members WHERE activity_id = ? AND user_id = ?",
            (int(activity_id), str(user_id)),
        )
        self.conn.commit()

    def update_member(self, activity_id, user_id, **fields):
        if not fields:
            return
        sets = ", ".join(f"{k} = ?" for k in fields)
        self.cur.execute(
            f"UPDATE activity_members SET {sets} WHERE activity_id = ? AND user_id = ?",
            (*fields.values(), int(activity_id), str(user_id)),
        )
        self.conn.commit()

    def set_ring(self, activity_id, assignments: list[tuple[str, str, int]]):
        """assignments: [(user_id, next_user_id, seq), ...] — 匹配环 / 接龙链一次写入。"""
        for uid, next_uid, seq in assignments:
            self.cur.execute(
                "UPDATE activity_members SET seq = ?, next_user_id = ?"
                " WHERE activity_id = ? AND user_id = ?",
                (int(seq), next_uid, int(activity_id), str(uid)),
            )
        self.conn.commit()

    def get_running_activities_for_user(self, user_id) -> list[dict]:
        return self._rows(
            "SELECT a.* FROM activities a JOIN activity_members m ON m.activity_id = a.id"
            " WHERE m.user_id = ? AND a.status = 'running' ORDER BY a.id DESC",
            (str(user_id),),
        )

    def get_running_activity_for_user_and_id(self, user_id, activity_id) -> dict | None:
        return self._row(
            "SELECT a.* FROM activities a JOIN activity_members m ON m.activity_id = a.id"
            " WHERE m.user_id = ? AND a.status = 'running' AND a.id = ?",
            (str(user_id), int(activity_id)),
        )
