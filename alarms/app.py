"""闹钟子应用：个人与群闹钟管理。"""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from alarms.alarm_service import cancel_alarm, create_alarm, list_alarms
from core.auth import verify_login_key

STATIC_DIR = Path(__file__).resolve().parent / "static"
SHARED_STATIC_DIR = Path(__file__).resolve().parent.parent / "core" / "web" / "static"

app = FastAPI(title="BotEro 闹钟", version="1.0.0")


def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    uid = verify_login_key(authorization[7:].strip())
    if uid is None:
        raise HTTPException(status_code=401, detail="密钥无效")
    return uid


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


@app.get("/api/me/alarms")
def api_alarms_list(user_id: Annotated[str, Depends(get_current_user_id)]):
    return list_alarms(user_id)


@app.post("/api/me/alarms")
def api_alarms_create(
    body: AlarmCreateIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _or_400(create_alarm, user_id, body.model_dump())


@app.delete("/api/me/alarms/{alarm_id}")
def api_alarms_cancel(
    alarm_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _or_400(cancel_alarm, user_id, alarm_id)


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "alarms.html")


app.mount("/shared", StaticFiles(directory=SHARED_STATIC_DIR), name="shared")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
