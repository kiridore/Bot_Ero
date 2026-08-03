"""活动数据读取（bot 写入，web 只读）。"""
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
    """全部活动：进行中（open/running）在前且附成员列表，归档/取消在后。"""
    acts = _rows(
        "SELECT a.id, a.type, a.title, a.description, a.status, a.group_id,"
        " a.signup_deadline, a.deadline, a.hours_per_user, a.created_at, a.finished_at,"
        " (SELECT COUNT(*) FROM activity_members m WHERE m.activity_id = a.id) AS member_count,"
        " (SELECT COUNT(*) FROM activity_members m WHERE m.activity_id = a.id AND m.status = 'done') AS done_count"
        " FROM activities a"
        " ORDER BY CASE a.status WHEN 'open' THEN 0 WHEN 'running' THEN 1 ELSE 2 END, a.id DESC"
    )
    for act in acts:
        if act["status"] in ("open", "running"):
            act["members"] = _rows(
                "SELECT user_id, nickname, seq, status FROM activity_members"
                " WHERE activity_id = ? ORDER BY seq ASC",
                (act["id"],),
            )
    return acts


def get_my_activities(user_id: str) -> list[dict]:
    """当前用户参加过的全部活动（含自己在其中的状态）。"""
    return _rows(
        "SELECT a.id, a.type, a.title, a.status, a.signup_deadline, a.deadline,"
        " a.finished_at, m.status AS my_status, m.seq AS my_seq,"
        " m.submitted_at AS my_submitted_at,"
        " (SELECT COUNT(*) FROM activity_members mm WHERE mm.activity_id = a.id) AS member_count,"
        " (SELECT COUNT(*) FROM activity_members mm WHERE mm.activity_id = a.id"
        "   AND mm.status = 'done') AS done_count"
        " FROM activities a JOIN activity_members m ON m.activity_id = a.id"
        " WHERE m.user_id = ? ORDER BY a.id DESC",
        (str(user_id),),
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
