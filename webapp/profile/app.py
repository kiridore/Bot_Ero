"""个人中心子应用：个人主页/打卡/商店/称号/设置 5 域聚合。"""

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel

from webapp.gallery.repository import (
    CheckinImage,
    fetch_checkins_paginated,
    fetch_user_settlement_day,
)
from core import user_settings as user_settings_mod
from core.onebot_client import resolve_display_name
from core.web.auth_deps import get_current_user_id
from webapp.profile.avatar_service import cached_avatar_path
from webapp.profile.checkin_service import get_checkin_status, perform_checkin, save_uploaded_images
from webapp.profile import email_service
from webapp.profile.profile_service import build_profile
from webapp.profile.redeem_service import redeem_code, redeem_history
from webapp.profile.shop_service import get_shop, redeem_shop_item
from webapp.profile.title_settings import (
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


class CheckinPageOut(BaseModel):
    page: int
    page_size: int
    total: int
    has_more: bool
    items: list[CheckinItemOut]


CHECKIN_PAGE_SIZE = 24


class DayCheckinsOut(BaseModel):
    date: str
    items: list[CheckinItemOut]


class StreaksOut(BaseModel):
    longest_daily: int
    current_daily: int
    longest_weekly: int
    current_weekly: int


class CheckinStatusOut(BaseModel):
    week_start: str
    week_end: str
    week_image_count: int
    is_first_this_week: bool
    streaks: StreaksOut
    max_images: int
    max_bytes: int


class TitleBriefOut(BaseModel):
    id: int
    name: str
    rarity: str
    description: str


class CheckinSubmitOut(BaseModel):
    success: bool
    image_count: int
    is_first_this_week: bool
    week_total_images: int
    bonus_total: int
    bonus_lines: list[str]
    unlocked_titles: list[TitleBriefOut]
    streaks: StreaksOut
    summary: str


class ShopItemOut(BaseModel):
    id: str
    description: str
    cost: int
    stock: int | None = None
    stock_label: str
    owned: bool
    can_buy: bool
    affordable: bool


class ShopOut(BaseModel):
    points: int
    items: list[ShopItemOut]
    refresh_hint: str


class ShopRedeemOut(BaseModel):
    success: bool
    product_id: str
    message: str
    points: int


class RedeemHistoryItemOut(BaseModel):
    code: str
    used_at: str
    description: str


class RedeemHistoryOut(BaseModel):
    items: list[RedeemHistoryItemOut]


class RedeemCodeOut(BaseModel):
    success: bool
    message: str


class EquippedTitleOut(TitleBriefOut):
    slot: int


class UnlockedTitleSettingsOut(TitleBriefOut):
    equipped: bool


class TitleSettingsOut(BaseModel):
    max_equipped: int
    equipped: list[EquippedTitleOut]
    unlocked: list[UnlockedTitleSettingsOut]
    display_prefix: str


class HeatmapCellOut(BaseModel):
    date: str
    count: int
    level: int
    is_remedy: bool


class ProfileTitleOut(BaseModel):
    id: int
    name: str
    rarity: str
    description: str
    unlock_type: str
    unlocked: bool
    equipped: bool
    progress: float
    progress_current: int
    progress_target: int
    progress_hint: str | None = None


class ProfileOut(BaseModel):
    user_id: str
    display_name: str
    avatar_url: str
    year: int | None = None
    points: int
    total_checkin_images: int
    streaks: StreaksOut
    titles_unlocked: int
    titles_total: int
    heatmap: list[HeatmapCellOut]
    titles: list[ProfileTitleOut]


class EmailCodeOut(BaseModel):
    cooldown_seconds: int


class SuccessOut(BaseModel):
    success: bool


class EquippedTitlesIn(BaseModel):
    title_ids: list[int]


class EquipOneIn(BaseModel):
    title_id: int


class ShopRedeemIn(BaseModel):
    product_id: str


class RedeemCodeIn(BaseModel):
    code: str


class SettingsIn(BaseModel):
    privacy: dict | None = None


class SettingsOut(BaseModel):
    privacy: dict
    email: str | None = None
    email_bound_at: str | None = None


class EmailCodeIn(BaseModel):
    email: str = ""
    purpose: str = "bind"


class EmailBindIn(BaseModel):
    email: str
    code: str


class EmailUnbindIn(BaseModel):
    code: str


def _file_slug(content: str) -> str:
    return content.replace("{", "").replace("}", "").replace("-", "")


def _media_url(user_id: str, content: str) -> str:
    # 文件名来自 QQ 图片原名，可能含 $ [ ] % 等不安全字符（%1R 类非法转义会被 Caddy 400）
    return f"/media/{user_id}/{quote(_file_slug(content))}"


def _thumb_url(user_id: str, content: str) -> str:
    return f"/thumb/{user_id}/{quote(_file_slug(content))}"


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


@router.get("/api/me/profile", response_model=ProfileOut)
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


@router.get("/api/me/checkins", response_model=CheckinPageOut)
def api_my_checkins(
    user_id: Annotated[str, Depends(get_current_user_id)],
    page: int = Query(1, ge=1),
):
    items, total, has_more = fetch_checkins_paginated(
        user_id=user_id, page=page, page_size=CHECKIN_PAGE_SIZE
    )
    name = resolve_display_name(user_id)
    return CheckinPageOut(
        page=page,
        page_size=CHECKIN_PAGE_SIZE,
        total=total,
        has_more=has_more,
        items=[_checkin_to_out(it, name) for it in items],
    )


@router.get("/api/me/avatar.png")
def api_my_avatar_png(
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    path = cached_avatar_path(user_id)
    if path is None:
        raise HTTPException(status_code=404, detail="头像不可用")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=86400"})


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


@router.get("/api/me/checkin/status", response_model=CheckinStatusOut)
def api_checkin_status(user_id: Annotated[str, Depends(get_current_user_id)]):
    return get_checkin_status(user_id)


@router.post("/api/me/checkin", response_model=CheckinSubmitOut)
async def api_checkin_submit(
    user_id: Annotated[str, Depends(get_current_user_id)],
    files: list[UploadFile] = File(...),
):
    payloads: list[tuple[bytes, str | None]] = []
    for f in files:
        data = await f.read()
        payloads.append((data, f.content_type))
    # 阻塞工作（文件写 + SQLite + emit 自回环 HTTP）必须出事件循环：
    # 否则 perform_checkin 内的 emit_event 自 POST 本进程时，事件循环被阻塞无法
    # 服务该请求 → 互相等待双双超时，时间线事件丢失（打卡响应也卡 ~10s）
    names = await run_in_threadpool(_checkin_or_400, save_uploaded_images, user_id, payloads)
    return await run_in_threadpool(perform_checkin, user_id, names)


@router.get("/api/me/shop", response_model=ShopOut)
def api_shop(user_id: Annotated[str, Depends(get_current_user_id)]):
    return get_shop(user_id)


@router.post("/api/me/shop/redeem", response_model=ShopRedeemOut)
def api_shop_redeem(
    body: ShopRedeemIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _checkin_or_400(redeem_shop_item, user_id, body.product_id)


@router.get("/api/me/redeem/history", response_model=RedeemHistoryOut)
def api_redeem_history(user_id: Annotated[str, Depends(get_current_user_id)]):
    return redeem_history(user_id)


@router.post("/api/me/redeem", response_model=RedeemCodeOut)
def api_redeem(
    body: RedeemCodeIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    try:
        return redeem_code(user_id, body.code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/me/titles/settings", response_model=TitleSettingsOut)
def api_title_settings(user_id: Annotated[str, Depends(get_current_user_id)]):
    return get_title_settings(user_id)


@router.put("/api/me/titles/equipped", response_model=TitleSettingsOut)
def api_set_equipped(
    body: EquippedTitlesIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _title_settings_or_400(set_equipped_titles, user_id, body.title_ids)


@router.post("/api/me/titles/equip", response_model=TitleSettingsOut)
def api_equip_one(
    body: EquipOneIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _title_settings_or_400(equip_title, user_id, body.title_id)


@router.delete("/api/me/titles/equipped", response_model=TitleSettingsOut)
def api_clear_equipped(user_id: Annotated[str, Depends(get_current_user_id)]):
    return clear_equipped_titles(user_id)


@router.delete("/api/me/titles/equip/{title_id}", response_model=TitleSettingsOut)
def api_unequip_one(
    title_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _title_settings_or_400(unequip_title, user_id, title_id)


@router.get("/api/me/settings", response_model=SettingsOut)
def api_my_settings(user_id: Annotated[str, Depends(get_current_user_id)]):
    settings = user_settings_mod.get_settings(user_id)
    return SettingsOut(
        privacy=settings.get("privacy", {}),
        email=settings.get("email"),
        email_bound_at=settings.get("email_bound_at"),
    )


@router.post("/api/me/email/code", response_model=EmailCodeOut)
def api_email_code(
    body: EmailCodeIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    if body.purpose not in ("bind", "unbind"):
        raise HTTPException(status_code=400, detail="purpose 不合法")
    if not email_service.mail_enabled():
        raise HTTPException(status_code=503, detail="邮件功能未开启，请联系管理员")
    if body.purpose == "bind":
        email = body.email.strip()
        if not email_service.is_valid_email(email):
            raise HTTPException(status_code=400, detail="邮箱格式不正确")
    else:
        email = user_settings_mod.get_settings(user_id).get("email") or ""
        if not email:
            raise HTTPException(status_code=400, detail="当前未绑定邮箱")
    ok, err = email_service.issue_code(user_id, email, body.purpose)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    return {"cooldown_seconds": email_service.CODE_COOLDOWN_SECONDS}


@router.post("/api/me/email/bind", response_model=SuccessOut)
def api_email_bind(
    body: EmailBindIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    email = body.email.strip()
    if not email_service.is_valid_email(email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    ok, err = email_service.bind_email(user_id, email, body.code.strip())
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    return {"success": True}


@router.post("/api/me/email/unbind", response_model=SuccessOut)
def api_email_unbind(
    body: EmailUnbindIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    ok, err = email_service.unbind_email(user_id, body.code.strip())
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    return {"success": True}


@router.put("/api/me/settings", response_model=SettingsOut)
def api_update_settings(
    body: SettingsIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    patch = body.model_dump(exclude_none=True)
    merged = user_settings_mod.update_settings(user_id, patch)
    return SettingsOut(
        privacy=merged.get("privacy", {}),
        email=merged.get("email"),
        email_bound_at=merged.get("email_bound_at"),
    )


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
