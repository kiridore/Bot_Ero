"""个人中心子应用：个人主页/打卡/商店/称号/设置 5 域聚合。"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from gallery.repository import CheckinImage, fetch_user_settlement_day
from core import user_settings as user_settings_mod
from core.onebot_client import resolve_display_name
from core.web.auth_deps import get_current_user_id
from profile.checkin_service import get_checkin_status, perform_checkin, save_uploaded_images
from profile.profile_service import build_profile
from profile.shop_service import get_shop, redeem_shop_item
from profile.title_settings import (
    clear_equipped_titles,
    equip_title,
    get_title_settings,
    set_equipped_titles,
    unequip_title,
)
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


class DayCheckinsOut(BaseModel):
    date: str
    items: list[CheckinItemOut]


class EquippedTitlesIn(BaseModel):
    title_ids: list[int]


class EquipOneIn(BaseModel):
    title_id: int


class ShopRedeemIn(BaseModel):
    product_id: str


class SettingsIn(BaseModel):
    privacy: dict | None = None


class SettingsOut(BaseModel):
    privacy: dict


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


@router.get("/api/me/profile")
def api_my_profile(
    user_id: Annotated[str, Depends(get_current_user_id)],
    year: int | None = Query(None, ge=2000, le=2100),
):
    return build_profile(user_id, year)


@router.get("/api/me/day", response_model=DayCheckinsOut)
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


@router.get("/api/me/checkin/status")
def api_checkin_status(user_id: Annotated[str, Depends(get_current_user_id)]):
    return get_checkin_status(user_id)


@router.post("/api/me/checkin")
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


@router.get("/api/me/shop")
def api_shop(user_id: Annotated[str, Depends(get_current_user_id)]):
    return get_shop(user_id)


@router.post("/api/me/shop/redeem")
def api_shop_redeem(
    body: ShopRedeemIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _checkin_or_400(redeem_shop_item, user_id, body.product_id)


@router.get("/api/me/titles/settings")
def api_title_settings(user_id: Annotated[str, Depends(get_current_user_id)]):
    return get_title_settings(user_id)


@router.put("/api/me/titles/equipped")
def api_set_equipped(
    body: EquippedTitlesIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _title_settings_or_400(set_equipped_titles, user_id, body.title_ids)


@router.post("/api/me/titles/equip")
def api_equip_one(
    body: EquipOneIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _title_settings_or_400(equip_title, user_id, body.title_id)


@router.delete("/api/me/titles/equipped")
def api_clear_equipped(user_id: Annotated[str, Depends(get_current_user_id)]):
    return clear_equipped_titles(user_id)


@router.delete("/api/me/titles/equip/{title_id}")
def api_unequip_one(
    title_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _title_settings_or_400(unequip_title, user_id, title_id)


@router.get("/api/me/settings", response_model=SettingsOut)
def api_my_settings(user_id: Annotated[str, Depends(get_current_user_id)]):
    settings = user_settings_mod.get_settings(user_id)
    return SettingsOut(privacy=settings.get("privacy", {}))


@router.put("/api/me/settings", response_model=SettingsOut)
def api_update_settings(
    body: SettingsIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    patch = body.model_dump(exclude_none=True)
    merged = user_settings_mod.update_settings(user_id, patch)
    return SettingsOut(privacy=merged.get("privacy", {}))


@router.get("/profile")
def profile_page():
    page = STATIC_DIR / "profile.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少个人主页")
    return FileResponse(page)


@router.get("/profile/checkin")
def checkin_page():
    page = STATIC_DIR / "checkin.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少打卡页")
    return FileResponse(page)


@router.get("/profile/shop")
def shop_page():
    page = STATIC_DIR / "shop.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少商店页")
    return FileResponse(page)


@router.get("/profile/settings")
def settings_page():
    page = STATIC_DIR / "settings.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少设置页")
    return FileResponse(page)
