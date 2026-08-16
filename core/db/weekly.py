"""周报产物存储：data.db 的 weekly_reports 表。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime


class WeeklyReportManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cur = conn.cursor()

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def upsert(self, week_key: str, group_id: int, data: dict | str, created_at: str | None = None) -> None:
        if not isinstance(data, str):
            data = json.dumps(data, ensure_ascii=False)
        self.cur.execute(
            """
            INSERT INTO weekly_reports (week_key, group_id, data_json, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(week_key, group_id) DO UPDATE SET
                data_json = excluded.data_json,
                created_at = excluded.created_at
            """,
            (str(week_key), int(group_id), data, created_at or self._now()),
        )
        self.conn.commit()

    def get(self, week_key: str, group_id: int) -> dict | None:
        self.cur.execute(
            "SELECT week_key, group_id, data_json, created_at FROM weekly_reports"
            " WHERE week_key = ? AND group_id = ?",
            (str(week_key), int(group_id)),
        )
        row = self.cur.fetchone()
        if not row:
            return None
        return {
            "week_key": row[0],
            "group_id": int(row[1]),
            "data_json": json.loads(row[2]),
            "created_at": row[3],
        }

    def list(self, group_id: int) -> list[dict]:
        self.cur.execute(
            "SELECT week_key, group_id, data_json, created_at FROM weekly_reports"
            " WHERE group_id = ? ORDER BY week_key DESC",
            (int(group_id),),
        )
        out = []
        for row in self.cur.fetchall():
            out.append({
                "week_key": row[0],
                "group_id": int(row[1]),
                "data_json": json.loads(row[2]),
                "created_at": row[3],
            })
        return out

    def issue(self, group_id: int, week_key: str) -> int:
        """第 N 期 = 该群 week_key <= 当前 的期数。"""
        self.cur.execute(
            "SELECT COUNT(*) FROM weekly_reports WHERE group_id = ? AND week_key <= ?",
            (int(group_id), str(week_key)),
        )
        row = self.cur.fetchone()
        return 0 if row is None else int(row[0])
