"""留言簿子应用：匿名展示，登录后可留言与点赞。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.config import PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX
from core.database_manager import DbManager
from core.web.auth_deps import get_current_user_id, get_optional_user_id

router = APIRouter()


class GuestbookPostIn(BaseModel):
    content: str


def _or_400(fn, *args):
    try:
        return fn(*args)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/guestbook")
def api_guestbook_list(
    viewer_id: Annotated[str | None, Depends(get_optional_user_id)],
    page: int = Query(1, ge=1),
    page_size: int = Query(PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX),
):
    db = DbManager()
    return db.guestbook.list_entries(viewer_id, page, page_size)


@router.post("/api/guestbook")
def api_guestbook_post(
    body: GuestbookPostIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    db = DbManager()
    return _or_400(db.guestbook.post_entry, user_id, body.content)


@router.post("/api/guestbook/{entry_id}/like")
def api_guestbook_like(
    entry_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    db = DbManager()
    return _or_400(db.guestbook.like_entry, user_id, entry_id)
