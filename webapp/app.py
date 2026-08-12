from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.auth import verify_login_key
from core.onebot_client import resolve_avatar_url, resolve_display_name
from core.web.auth_deps import get_current_user_id
from webapp import STATIC_DIR

from webapp.gallery.app import router as gallery_router
from webapp.guestbook.app import router as guestbook_router
from webapp.profile.app import router as profile_router
from webapp.trpg.app import router as trpg_router
from webapp.alarms.app import router as alarms_router
from webapp.activities.app import router as activities_router
from webapp.live.app import router as live_router
from webapp.forum.app import router as forum_router
from webapp.timeline.app import router as timeline_router

SHARED_STATIC_DIR = Path(__file__).resolve().parent.parent / "core" / "web" / "static"

app = FastAPI(title="BotEro Web", version="1.0.0")


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


# 社区主页（时间线，登录可见；根域 / 由 Caddy 反代到本进程）
@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "timeline.html")


app.include_router(gallery_router)
app.include_router(guestbook_router)
app.include_router(profile_router)
app.include_router(trpg_router)
app.include_router(alarms_router)
app.include_router(activities_router)
app.include_router(live_router)
app.include_router(timeline_router)
app.include_router(forum_router)
app.mount("/shared", StaticFiles(directory=SHARED_STATIC_DIR), name="shared")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
