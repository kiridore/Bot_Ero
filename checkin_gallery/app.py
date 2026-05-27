from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from checkin_gallery import config
from checkin_gallery.config import PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX
from checkin_gallery.onebot_client import resolve_display_name
from checkin_gallery.repository import fetch_checkins_paginated, list_user_ids, resolve_image_path

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="BotEro 打卡图库", version="1.0.0")


class CheckinItemOut(BaseModel):
    id: int
    user_id: str
    display_name: str
    checkin_date: str
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


def _media_url(user_id: str, content: str) -> str:
    name = content.replace("{", "").replace("}", "").replace("-", "")
    return f"/media/{user_id}/{name}"


@app.get("/api/users", response_model=UserIdsOut)
def api_users():
    users = [
        UserOptionOut(user_id=uid, display_name=resolve_display_name(uid))
        for uid in list_user_ids()
    ]
    return UserIdsOut(users=users)


@app.get("/api/checkins", response_model=CheckinListOut)
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


@app.get("/media/{user_id}/{filename}")
def serve_media(user_id: str, filename: str):
    if ".." in user_id or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="非法路径")
    path = resolve_image_path(user_id, filename)
    if path is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    _assert_under_root(path)
    return FileResponse(path)


@app.get("/")
def index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.is_file():
        raise HTTPException(status_code=500, detail="缺少静态页面")
    return FileResponse(index_file)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
