from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from checkin_gallery import config
from checkin_gallery.auth import verify_login_key
from checkin_gallery.checkin_service import get_checkin_status, perform_checkin, save_uploaded_images
from checkin_gallery.config import PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX
from checkin_gallery.onebot_client import resolve_avatar_url, resolve_display_name
from checkin_gallery.profile_service import build_profile
from checkin_gallery.alarm_service import cancel_alarm, create_alarm, list_alarms
from checkin_gallery.shop_service import get_shop, redeem_shop_item
from checkin_gallery.title_settings import (
    clear_equipped_titles,
    equip_title,
    get_title_settings,
    set_equipped_titles,
    unequip_title,
)
from checkin_gallery.repository import (
    CheckinImage,
    fetch_checkins_paginated,
    fetch_user_settlement_day,
    list_user_ids,
    resolve_image_path,
)
from checkin_gallery.thumbnails import ensure_thumbnail

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="BotEro 打卡图库", version="1.0.0")


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


class LoginIn(BaseModel):
    key: str


class SessionOut(BaseModel):
    user_id: str
    display_name: str
    avatar_url: str
    token: str


class DayCheckinsOut(BaseModel):
    date: str
    items: list[CheckinItemOut]


class EquippedTitlesIn(BaseModel):
    title_ids: list[int]


class EquipOneIn(BaseModel):
    title_id: int


class ShopRedeemIn(BaseModel):
    product_id: str


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


def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    uid = verify_login_key(authorization[7:].strip())
    if uid is None:
        raise HTTPException(status_code=401, detail="密钥无效")
    return uid


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


@app.get("/api/me/profile")
def api_my_profile(
    user_id: Annotated[str, Depends(get_current_user_id)],
    year: int | None = Query(None, ge=2000, le=2100),
):
    return build_profile(user_id, year)


@app.get("/api/me/day", response_model=DayCheckinsOut)
def api_my_day(
    user_id: Annotated[str, Depends(get_current_user_id)],
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    items = fetch_user_settlement_day(user_id, date)
    name = resolve_display_name(user_id)
    return DayCheckinsOut(
        date=date,
        items=[_checkin_to_out(it, name) for it in items],
    )


def _title_settings_or_400(fn, user_id: str, *args):
    try:
        return fn(user_id, *args)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _checkin_or_400(fn, *args):
    try:
        return fn(*args)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/me/checkin/status")
def api_checkin_status(user_id: Annotated[str, Depends(get_current_user_id)]):
    return get_checkin_status(user_id)


@app.post("/api/me/checkin")
async def api_checkin_submit(
    user_id: Annotated[str, Depends(get_current_user_id)],
    files: list[UploadFile] = File(...),
):
    payloads: list[tuple[bytes, str | None]] = []
    for f in files:
        data = await f.read()
        payloads.append((data, f.content_type))
    names = _checkin_or_400(save_uploaded_images, user_id, payloads)
    return perform_checkin(user_id, names)


@app.get("/api/me/shop")
def api_shop(user_id: Annotated[str, Depends(get_current_user_id)]):
    return get_shop(user_id)


@app.post("/api/me/shop/redeem")
def api_shop_redeem(
    body: ShopRedeemIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _checkin_or_400(redeem_shop_item, user_id, body.product_id)


@app.get("/api/me/alarms")
def api_alarms_list(user_id: Annotated[str, Depends(get_current_user_id)]):
    return list_alarms(user_id)


@app.post("/api/me/alarms")
def api_alarms_create(
    body: AlarmCreateIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _checkin_or_400(create_alarm, user_id, body.model_dump())


@app.delete("/api/me/alarms/{alarm_id}")
def api_alarms_cancel(
    alarm_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _checkin_or_400(cancel_alarm, user_id, alarm_id)


@app.get("/api/me/titles/settings")
def api_title_settings(user_id: Annotated[str, Depends(get_current_user_id)]):
    return get_title_settings(user_id)


@app.put("/api/me/titles/equipped")
def api_set_equipped(
    body: EquippedTitlesIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _title_settings_or_400(set_equipped_titles, user_id, body.title_ids)


@app.post("/api/me/titles/equip")
def api_equip_one(
    body: EquipOneIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _title_settings_or_400(equip_title, user_id, body.title_id)


@app.delete("/api/me/titles/equipped")
def api_clear_equipped(user_id: Annotated[str, Depends(get_current_user_id)]):
    return clear_equipped_titles(user_id)


@app.delete("/api/me/titles/equip/{title_id}")
def api_unequip_one(
    title_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _title_settings_or_400(unequip_title, user_id, title_id)


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


@app.get("/thumb/{user_id}/{filename}")
def serve_thumb(user_id: str, filename: str):
    source = _resolve_and_guard(user_id, filename)
    try:
        thumb = ensure_thumbnail(source)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="缩略图生成失败") from exc
    return FileResponse(thumb, media_type="image/jpeg")


@app.get("/media/{user_id}/{filename}")
def serve_media(user_id: str, filename: str):
    path = _resolve_and_guard(user_id, filename)
    return FileResponse(path)


@app.get("/")
def index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.is_file():
        raise HTTPException(status_code=500, detail="缺少静态页面")
    return FileResponse(index_file)


@app.get("/profile")
def profile_page():
    page = STATIC_DIR / "profile.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少个人主页")
    return FileResponse(page)


@app.get("/profile/settings")
def profile_settings_page():
    page = STATIC_DIR / "settings.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少设置页")
    return FileResponse(page)


@app.get("/profile/checkin")
def profile_checkin_page():
    page = STATIC_DIR / "checkin.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少打卡页")
    return FileResponse(page)


@app.get("/profile/shop")
def profile_shop_page():
    page = STATIC_DIR / "shop.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少商店页")
    return FileResponse(page)


@app.get("/profile/alarms")
def profile_alarms_page():
    page = STATIC_DIR / "alarms.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少闹钟页")
    return FileResponse(page)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
