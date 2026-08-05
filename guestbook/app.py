"""留言簿子应用：匿名展示，登录后可留言与点赞。"""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.auth import verify_login_key
from core.config import PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX
from core.database_manager import DbManager

STATIC_DIR = Path(__file__).resolve().parent / "static"
SHARED_STATIC_DIR = Path(__file__).resolve().parent.parent / "core" / "web" / "static"

app = FastAPI(title="BotEro 留言簿", version="1.0.0")


def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    uid = verify_login_key(authorization[7:].strip())
    if uid is None:
        raise HTTPException(status_code=401, detail="密钥无效")
    return uid


def get_optional_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return verify_login_key(authorization[7:].strip())


class GuestbookPostIn(BaseModel):
    content: str


def _or_400(fn, *args):
    try:
        return fn(*args)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/guestbook")
def api_guestbook_list(
    viewer_id: Annotated[str | None, Depends(get_optional_user_id)],
    page: int = Query(1, ge=1),
    page_size: int = Query(PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX),
):
    db = DbManager()
    return db.guestbook.list_entries(viewer_id, page, page_size)


@app.post("/api/guestbook")
def api_guestbook_post(
    body: GuestbookPostIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    db = DbManager()
    return _or_400(db.guestbook.post_entry, user_id, body.content)


@app.post("/api/guestbook/{entry_id}/like")
def api_guestbook_like(
    entry_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    db = DbManager()
    return _or_400(db.guestbook.like_entry, user_id, entry_id)


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "guestbook.html")


app.mount("/shared", StaticFiles(directory=SHARED_STATIC_DIR), name="shared")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
