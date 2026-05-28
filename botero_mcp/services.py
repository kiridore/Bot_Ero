"""BotEro MCP 业务层：复用 checkin_gallery 与 group_alarm 逻辑。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from core.database_manager import DbManager
from core.utils import get_monday_to_monday

from checkin_gallery.alarm_service import cancel_alarm, create_alarm, list_alarms
from checkin_gallery.checkin_service import get_checkin_status
from checkin_gallery.repository import fetch_checkins_paginated

_GROUP_ALARM_PATH = Path(__file__).resolve().parent.parent / "plugins" / "group_alarm.py"
_REMEDY = "remedy_checkin"


def _load_group_alarm():
    spec = importlib.util.spec_from_file_location("botero_group_alarm_mcp", _GROUP_ALARM_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 group_alarm 模块")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ok(data: Any) -> str:
    return json.dumps({"ok": True, "data": data}, ensure_ascii=False, indent=2)


def _err(message: str) -> str:
    return json.dumps({"ok": False, "error": message}, ensure_ascii=False, indent=2)


def alarm_list(user_id: str) -> str:
    try:
        return _ok(list_alarms(user_id))
    except Exception as exc:
        return _err(str(exc))


def alarm_create_structured(user_id: str, payload: dict[str, Any]) -> str:
    try:
        return _ok(create_alarm(user_id, payload))
    except ValueError as exc:
        return _err(str(exc))
    except Exception as exc:
        return _err(str(exc))


def alarm_create_from_text(user_id: str, schedule_text: str) -> str:
    body = (schedule_text or "").strip()
    if not body:
        return _err("schedule_text 不能为空（与机器人 /闹钟 后正文格式相同）")
    try:
        ga = _load_group_alarm()
        parsed = ga._parse_create_body(body)
        if isinstance(parsed, str):
            return _err(parsed)
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
        return _ok(
            {
                "id": aid,
                "message": (
                    f"已设置闹钟 #{aid}，将于 {fire.strftime('%Y-%m-%d %H:%M')} 提醒你{extra}："
                    f"「{clean_content}」"
                ),
            }
        )
    except Exception as exc:
        return _err(str(exc))


def alarm_cancel(user_id: str, alarm_id: int) -> str:
    try:
        return _ok(cancel_alarm(user_id, alarm_id))
    except ValueError as exc:
        return _err(str(exc))
    except Exception as exc:
        return _err(str(exc))


def checkin_weekly_status(user_id: str) -> str:
    try:
        return _ok(get_checkin_status(user_id))
    except Exception as exc:
        return _err(str(exc))


def checkin_list_records(
    user_id: str,
    *,
    year: int | None = None,
    page: int = 1,
    page_size: int = 20,
    images_only: bool = False,
) -> str:
    try:
        page = max(1, int(page))
        page_size = max(1, min(50, int(page_size)))
        items, total, has_more = fetch_checkins_paginated(
            user_id=user_id,
            year=year,
            page=page,
            page_size=page_size,
            only_with_file=images_only,
        )
        rows = [
            {
                "id": it.id,
                "checkin_date": it.checkin_date,
                "has_local_image": it.image_path is not None,
            }
            for it in items
        ]
        return _ok(
            {
                "items": rows,
                "total": total,
                "page": page,
                "page_size": page_size,
                "has_more": has_more,
                "year": year,
            }
        )
    except Exception as exc:
        return _err(str(exc))


def checkin_list_week_members() -> str:
    try:
        start_date, end_date = get_monday_to_monday()
        db = DbManager()
        rows = db.search_all_user_checkin_range(start_date, end_date)
        user_map: dict[str, str] = {}
        for row in rows:
            uid = str(row[1])
            content = row[3] if len(row) > 3 else ""
            if content == _REMEDY:
                continue
            ts = row[2]
            if uid not in user_map or ts < user_map[uid]:
                user_map[uid] = ts
        members = [
            {"user_id": uid, "first_checkin_at": ts}
            for uid, ts in sorted(user_map.items(), key=lambda x: x[1])
        ]
        return _ok(
            {
                "week_start": start_date.split(" ")[0],
                "week_end": end_date.split(" ")[0],
                "count": len(members),
                "members": members,
            }
        )
    except Exception as exc:
        return _err(str(exc))
