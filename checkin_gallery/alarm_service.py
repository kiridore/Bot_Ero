"""网页端闹钟（复用 plugins/group_alarm 解析逻辑，避免导入 plugins 包）。"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any

from core.database_manager import DbManager

_GROUP_ALARM_PATH = Path(__file__).resolve().parent.parent / "plugins" / "group_alarm.py"

_TIME_RE = re.compile(r"^([0-1]?\d|2[0-3]):([0-5]\d)$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_WEEKDAY_CN = ("一", "二", "三", "四", "五", "六", "日")


def _load_group_alarm():
    spec = importlib.util.spec_from_file_location("botero_group_alarm", _GROUP_ALARM_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 group_alarm 模块")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _normalize_time(raw: str | None) -> str | None:
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    m = _TIME_RE.match(text)
    if not m:
        raise ValueError("时间格式须为 HH:MM（00:00–23:59）")
    return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"


def _positive_int(value: Any, name: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    try:
        n = int(value or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}须为整数") from exc
    if n < minimum:
        raise ValueError(f"{name}须至少为 {minimum}")
    if maximum is not None and n > maximum:
        raise ValueError(f"{name}须在 {minimum}–{maximum} 之间")
    return n


def _build_alarm_body(payload: dict[str, Any]) -> str:
    content = str(payload.get("content") or "").strip()
    if not content:
        raise ValueError("请填写提醒内容")

    schedule_type = str(payload.get("schedule_type") or "").strip()
    time_str = _normalize_time(payload.get("time"))
    prefix = ""

    if schedule_type == "once_date":
        date = str(payload.get("date") or "").strip()
        if not _DATE_RE.match(date):
            raise ValueError("请选择有效日期")
        prefix = date
        if time_str:
            prefix = f"{prefix} {time_str}"
    elif schedule_type == "once_relative":
        years = _positive_int(payload.get("years"), "年")
        months = _positive_int(payload.get("months"), "月")
        days = _positive_int(payload.get("days"), "日")
        hours = _positive_int(payload.get("hours"), "小时")
        minutes = _positive_int(payload.get("minutes"), "分钟")
        if not any((years, months, days, hours, minutes)):
            raise ValueError("请至少填写一项相对时间")
        parts: list[str] = []
        if years:
            parts.append(f"{years}年")
        if months:
            parts.append(f"{months}月")
        if days:
            parts.append(f"{days}日")
        if hours:
            parts.append(f"{hours}小时")
        if minutes:
            parts.append(f"{minutes}分钟")
        prefix = "".join(parts) + "后"
    elif schedule_type == "once_today":
        if not time_str:
            raise ValueError("请选择时刻")
        prefix = time_str
    elif schedule_type == "daily":
        prefix = "每天"
        if time_str:
            prefix = f"{prefix} {time_str}"
    elif schedule_type == "interval_days":
        n = _positive_int(payload.get("interval_days"), "间隔天数", minimum=1)
        prefix = "每天" if n == 1 else f"每{n}天"
        if time_str:
            prefix = f"{prefix} {time_str}"
    elif schedule_type == "weekly":
        wd = _positive_int(payload.get("weekday"), "星期", minimum=1, maximum=7)
        prefix = f"每周{_WEEKDAY_CN[wd - 1]}"
        if time_str:
            prefix = f"{prefix} {time_str}"
    elif schedule_type == "monthly":
        dom = _positive_int(payload.get("day"), "日", minimum=1, maximum=31)
        prefix = f"每月{dom}日"
        if time_str:
            prefix = f"{prefix} {time_str}"
    elif schedule_type == "yearly":
        mo = _positive_int(payload.get("month"), "月", minimum=1, maximum=12)
        dom = _positive_int(payload.get("day"), "日", minimum=1, maximum=31)
        prefix = f"每年{mo}月{dom}日"
        if time_str:
            prefix = f"{prefix} {time_str}"
    else:
        raise ValueError("未知的触发方式")

    return f"{prefix} {content}".strip()


def _format_alarm_row(row: tuple, format_recur) -> dict:
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
    return {"items": items, "min_lead_minutes": 5}


def create_alarm(user_id: str, payload: dict[str, Any]) -> dict:
    body = _build_alarm_body(payload)
    ga = _load_group_alarm()
    parsed = ga._parse_create_body(body)
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
