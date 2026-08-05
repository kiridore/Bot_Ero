"""活动子应用：接龙与匹配活动的作品归档。"""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.auth import verify_login_key
from core.config import ACTIVITY_ROOT
from core.database_manager import DbManager
from core.onebot_client import resolve_avatar_url, resolve_display_name

STATIC_DIR = Path(__file__).resolve().parent / "static"
SHARED_STATIC_DIR = Path(__file__).resolve().parent.parent / "core" / "web" / "static"

app = FastAPI(title="BotEro 活动", version="1.0.0")


def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    uid = verify_login_key(authorization[7:].strip())
    if uid is None:
        raise HTTPException(status_code=401, detail="密钥无效")
    return uid


class LoginIn(BaseModel):
    key: str


class SessionOut(BaseModel):
    user_id: str
    display_name: str
    avatar_url: str
    token: str


@app.post("/api/auth/login", response_model=SessionOut)
def api_login(body: LoginIn):
    uid = verify_login_key(body.key.strip())
    if uid is None:
        raise HTTPException(status_code=401, detail="密钥无效")
    token = body.key.strip()
    return SessionOut(
        user_id=uid,
        display_name=resolve_display_name(uid),
        avatar_url=resolve_avatar_url(uid),
        token=token,
    )


@app.get("/api/auth/me", response_model=SessionOut)
def api_me(user_id: Annotated[str, Depends(get_current_user_id)]):
    return SessionOut(
        user_id=user_id,
        display_name=resolve_display_name(user_id),
        avatar_url=resolve_avatar_url(user_id),
        token="",
    )


@app.get("/api/activities")
def api_activities():
    db = DbManager()
    return {"items": db.activity.list_activities()}


@app.get("/api/me/activities")
def api_my_activities(user_id: Annotated[str, Depends(get_current_user_id)]):
    db = DbManager()
    return {"items": db.activity.get_my_activities(user_id)}


@app.get("/api/activities/{activity_id}")
def api_activity_detail(activity_id: int):
    db = DbManager()
    act = db.activity.get_activity(activity_id)
    if not act:
        raise HTTPException(status_code=404, detail="活动不存在")
    for m in act["members"]:
        m["images"] = [
            f"/archive/{activity_id}/media/{name}" for name in m.get("images", [])
        ]
    return act


def _assert_under_activity_root(path: Path) -> None:
    try:
        path.resolve().relative_to(ACTIVITY_ROOT.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="禁止访问") from exc


@app.get("/archive/{activity_id}/media/{filename}")
def serve_activity_media(activity_id: int, filename: str):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="非法路径")
    path = ACTIVITY_ROOT / str(activity_id) / "imgs" / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="图片不存在")
    _assert_under_activity_root(path)
    return FileResponse(path)


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "activities.html")


@app.get("/{activity_id}")
def activity_detail_page(activity_id: int):
    db = DbManager()
    if db.activity.get_activity(activity_id) is None:
        raise HTTPException(status_code=404, detail="活动不存在")
    page = STATIC_DIR / "activities_detail.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少活动详情页")
    return FileResponse(page)


app.mount("/shared", StaticFiles(directory=SHARED_STATIC_DIR), name="shared")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
