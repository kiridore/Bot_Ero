"""网页端闹钟（复用 plugins/group_alarm 解析逻辑，避免导入 plugins 包）。"""

from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path

from core.database_manager import DbManager

_GROUP_ALARM_PATH = Path(__file__).resolve().parent.parent / "plugins" / "group_alarm.py"

_USAGE_HINT = (
    "语法与机器人 /闹钟 一致，例如：每天 8:00 起床、30分钟后 开会、"
    "2026-06-01 9:00 交报告。触发时刻须距当前至少 5 分钟。"
)


def _load_group_alarm():
    spec = importlib.util.spec_from_file_location("botero_group_alarm", _GROUP_ALARM_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 group_alarm 模块")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _format_alarm_row(
    row: tuple,
    format_recur,
) -> dict:
    rid, fat, content, is_rec, rk, ra, rb, rc, is_priv, gid = row
    is_recurring = int(is_rec or 0) and int(rk or 0) > 0
    recur_desc = None
    if is_recurring:
        recur_desc = format_recur(int(rk), int(ra or 0), int(rb or 0), int(rc or 0))
    fire_at = (fat or "")[:16]
    scope = "私聊" if int(is_priv or 0) else f"群 {gid}"
    preview = content if len(content) <= 80 else content[:80] + "…"
    return {
        "id": int(rid),
        "fire_at": fire_at,
        "content": content,
        "preview": preview,
        "is_recurring": is_recurring,
        "recur_desc": recur_desc,
        "is_private": bool(int(is_priv or 0)),
        "group_id": int(gid or 0),
        "scope": scope,
    }


def list_alarms(user_id: str) -> dict:
    ga = _load_group_alarm()
    db = DbManager()
    db.cur.execute(
        """
        SELECT id, fire_at, content, is_recurring,
               recur_kind, recur_a, recur_b, recur_c,
               is_private, group_id
        FROM group_alarms
        WHERE creator_user_id = ? AND fired = 0
        ORDER BY fire_at ASC
        """,
        (int(user_id),),
    )
    rows = db.cur.fetchall()
    items = [_format_alarm_row(r, ga._format_recur_desc) for r in rows]
    return {"items": items, "usage_hint": _USAGE_HINT}


def create_alarm(user_id: str, body: str) -> dict:
    text = (body or "").strip()
    if not text:
        raise ValueError("请填写闹钟内容")

    ga = _load_group_alarm()
    parsed = ga._parse_create_body(text)
    if isinstance(parsed, str):
        raise ValueError(parsed)

    fire, clean_content, recur = parsed
    db = DbManager()
    aid = db.add_group_alarm(
        int(user_id),
        fire,
        clean_content,
        group_id=None,
        is_private=True,
        recur=recur,
    )
    if recur:
        k, a, b, c = recur
        extra = f"（{ga._format_recur_desc(k, a, b, c)} 循环）"
    else:
        extra = ""
    return {
        "id": aid,
        "message": (
            f"已设置闹钟 #{aid}，将于 {fire.strftime('%Y-%m-%d %H:%M')} 提醒你{extra}："
            f"「{clean_content}」"
        ),
    }


def cancel_alarm(user_id: str, alarm_id: int) -> dict:
    db = DbManager()
    db.cur.execute(
        """
        SELECT is_private, group_id
        FROM group_alarms
        WHERE id = ? AND creator_user_id = ? AND fired = 0
        """,
        (int(alarm_id), int(user_id)),
    )
    row = db.cur.fetchone()
    if not row:
        raise ValueError("取消失败：编号不存在、已触发或不是你创建的闹钟")

    is_priv, gid = int(row[0] or 0), row[1]
    cancel_gid = None if is_priv else int(gid)
    ok = db.cancel_group_alarm(int(alarm_id), int(user_id), cancel_gid)
    if not ok:
        raise ValueError("取消失败：编号不存在、已触发或不是你创建的闹钟")
    return {"message": f"已取消闹钟 #{alarm_id}"}
