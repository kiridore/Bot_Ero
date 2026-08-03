"""活动归档读取（bot 写入，web 只读）。"""
import json
import sqlite3

from checkin_gallery import config

DB_PATH = config.DB_PATH


def _rows(sql, params=()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def list_activities() -> list[dict]:
    return _rows(
        "SELECT a.id, a.type, a.title, a.group_id, a.created_at, a.finished_at,"
        " (SELECT COUNT(*) FROM activity_members m WHERE m.activity_id = a.id) AS member_count,"
        " (SELECT COUNT(*) FROM activity_members m WHERE m.activity_id = a.id AND m.status = 'done') AS done_count"
        " FROM activities a WHERE a.status = 'finished' ORDER BY a.id DESC"
    )


def get_activity(activity_id: int) -> dict | None:
    rows = _rows("SELECT * FROM activities WHERE id = ?", (activity_id,))
    if not rows:
        return None
    act = rows[0]
    act["members"] = _rows(
        "SELECT user_id, nickname, seq, status, submitted_at, content, images"
        " FROM activity_members WHERE activity_id = ? ORDER BY seq ASC",
        (activity_id,),
    )
    for m in act["members"]:
        try:
            m["images"] = json.loads(m["images"]) if m.get("images") else []
        except (TypeError, ValueError):
            m["images"] = []
    return act
