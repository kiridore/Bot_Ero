from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from webapp.gallery import config
from webapp.gallery.config import PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX
from core.onebot_client import resolve_display_name
from webapp.gallery.repository import (
    CheckinImage,
    fetch_checkins_paginated,
    list_user_ids,
    resolve_image_path,
)
from webapp.gallery.thumbnails import ensure_thumbnail
from webapp import STATIC_DIR

router = APIRouter()

class CheckinItemOut(BaseModel):
    id: int
    user_id: str
    display_name: str
    checkin_date: str
    thumbnail_url: str
    image_url: str
    has_file: bool

class CheckinListOut(BaseModel):
    items: list[CheckinItemOut]
    total: int
    page: int
    page_size: int
    has_more: bool

class UserOptionOut(BaseModel):
    user_id: str
    display_name: str

class UserIdsOut(BaseModel):
    users: list[UserOptionOut]


def _file_slug(content: str) -> str:
    return content.replace("{", "").replace("}", "").replace("-", "")

def _media_url(user_id: str, content: str) -> str:
    return f"/media/{user_id}/{_file_slug(content)}"

def _thumb_url(user_id: str, content: str) -> str:
    return f"/thumb/{user_id}/{_file_slug(content)}"


def _checkin_to_out(item: CheckinImage, display_name: str) -> CheckinItemOut:
    return CheckinItemOut(
        id=item.id,
        user_id=item.user_id,
        display_name=display_name,
        checkin_date=item.checkin_date,
        thumbnail_url=_thumb_url(item.user_id, item.content),
        image_url=_media_url(item.user_id, item.content),
        has_file=item.image_path is not None,
    )


@router.get("/api/users", response_model=UserIdsOut)
def api_users():
    users = [
        UserOptionOut(user_id=uid, display_name=resolve_display_name(uid))
        for uid in list_user_ids()
    ]
    return UserIdsOut(users=users)


@router.get("/api/checkins", response_model=CheckinListOut)
def api_checkins(
    page: int = Query(1, ge=1),
    page_size: int = Query(PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX),
    user_id: str | None = None,
    year: int | None = Query(None, ge=2000, le=2100),
    only_with_file: bool = True,
):
    items, total, has_more = fetch_checkins_paginated(
        user_id=user_id,
        year=year,
        page=page,
        page_size=page_size,
        only_with_file=only_with_file,
    )
    name_cache: dict[str, str] = {}
    out: list[CheckinItemOut] = []
    for item in items:
        if item.user_id not in name_cache:
            name_cache[item.user_id] = resolve_display_name(item.user_id)
        out.append(
            CheckinItemOut(
                id=item.id,
                user_id=item.user_id,
                display_name=name_cache[item.user_id],
                checkin_date=item.checkin_date,
                thumbnail_url=_thumb_url(item.user_id, item.content),
                image_url=_media_url(item.user_id, item.content),
                has_file=item.image_path is not None,
            )
        )
    return CheckinListOut(
        items=out,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


def _assert_under_root(path: Path) -> None:
    try:
        path.resolve().relative_to(config.IMAGE_ROOT.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="禁止访问") from exc


def _resolve_and_guard(user_id: str, filename: str) -> Path:
    if ".." in user_id or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="非法路径")
    path = resolve_image_path(user_id, filename)
    if path is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    _assert_under_root(path)
    return path


@router.get("/thumb/{user_id}/{filename}")
def serve_thumb(user_id: str, filename: str):
    source = _resolve_and_guard(user_id, filename)
    try:
        thumb = ensure_thumbnail(source)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="缩略图生成失败") from exc
    return FileResponse(thumb, media_type="image/jpeg")


@router.get("/media/{user_id}/{filename}")
def serve_media(user_id: str, filename: str):
    path = _resolve_and_guard(user_id, filename)
    return FileResponse(path)


@router.get("/gallery")
def gallery_page():
    page = STATIC_DIR / "index.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少静态页面")
    return FileResponse(page)
