"""闹钟子应用：个人与群闹钟管理。"""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from webapp.alarms.alarm_service import (
    calendar_month,
    cancel_alarm,
    create_alarm,
    list_alarms,
    update_alarm,
)
from core.web.auth_deps import get_current_user_id
from webapp import STATIC_DIR

router = APIRouter()

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class AlarmCreateIn(BaseModel):
    content: str
    schedule_type: str
    date: str | None = None
    time: str | None = None
    years: int = 0
    months: int = 0
    days: int = 0
    hours: int = 0
    minutes: int = 0
    interval_days: int | None = None
    weekday: int | None = None
    month: int | None = None
    day: int | None = None
    scope: str = "private"


def _or_400(fn, *args):
    try:
        return fn(*args)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/me/alarms")
def api_alarms_list(user_id: Annotated[str, Depends(get_current_user_id)]):
    return list_alarms(user_id)


@router.get("/api/me/calendar")
def api_calendar(
    user_id: Annotated[str, Depends(get_current_user_id)],
    month: str = Query(...),
):
    if not _MONTH_RE.match(month):
        raise HTTPException(status_code=400, detail="month 须为 YYYY-MM")
    return calendar_month(user_id, month)


@router.post("/api/me/alarms")
def api_alarms_create(
    body: AlarmCreateIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _or_400(create_alarm, user_id, body.model_dump())


@router.put("/api/me/alarms/{alarm_id}")
def api_alarms_update(
    alarm_id: int,
    body: AlarmCreateIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _or_400(update_alarm, user_id, alarm_id, body.model_dump())


@router.delete("/api/me/alarms/{alarm_id}")
def api_alarms_cancel(
    alarm_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _or_400(cancel_alarm, user_id, alarm_id)


@router.get("/profile/schedule")
def schedule_page():
    page = STATIC_DIR / "schedule.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少静态页面")
    return FileResponse(page)


@router.get("/alarms")
def alarms_page():
    """旧闹钟页：302 到日程页（保留书签兼容）。"""
    return RedirectResponse("/profile/schedule", status_code=302)
