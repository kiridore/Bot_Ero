"""闹钟子应用：个人与群闹钟管理。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from alarms.alarm_service import cancel_alarm, create_alarm, list_alarms
from core.web.auth_deps import get_current_user_id

router = APIRouter()


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


def _or_400(fn, *args):
    try:
        return fn(*args)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/me/alarms")
def api_alarms_list(user_id: Annotated[str, Depends(get_current_user_id)]):
    return list_alarms(user_id)


@router.post("/api/me/alarms")
def api_alarms_create(
    body: AlarmCreateIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _or_400(create_alarm, user_id, body.model_dump())


@router.delete("/api/me/alarms/{alarm_id}")
def api_alarms_cancel(
    alarm_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _or_400(cancel_alarm, user_id, alarm_id)
