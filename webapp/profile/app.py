"""个人中心子应用：个人主页/打卡/商店/称号/设置 5 域聚合。"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from webapp.gallery.repository import (
    CheckinImage,
    fetch_checkins_paginated,
    fetch_user_settlement_day,
)
from core import user_settings as user_settings_mod
from core.onebot_client import resolve_display_name
from core.web.auth_deps import get_current_user_id
from webapp.profile.checkin_service import get_checkin_status, perform_checkin, save_uploaded_images
from webapp.profile import email_service
from webapp.profile.profile_service import build_profile
from webapp.profile.share_service import build_share_png
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
    has_more: bool
    items: list[CheckinItemOut]


CHECKIN_PAGE_SIZE = 24


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


@router.get("/api/me/checkins", response_model=CheckinPageOut)
def api_my_checkins(
    user_id: Annotated[str, Depends(get_current_user_id)],
    page: int = Query(1, ge=1),
):
    items, _total, has_more = fetch_checkins_paginated(
        user_id=user_id, page=page, page_size=CHECKIN_PAGE_SIZE
    )
    name = resolve_display_name(user_id)
    return CheckinPageOut(
        page=page,
        has_more=has_more,
        items=[_checkin_to_out(it, name) for it in items],
    )


@router.get("/api/me/checkin/{record_id}/share.png")
def api_checkin_share_png(
    record_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    data = build_share_png(record_id, user_id)
    if data is None:
        raise HTTPException(status_code=404, detail="打卡记录不存在")
    return Response(
        content=data,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=300"},
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
    # 阻塞工作（文件写 + SQLite + emit 自回环 HTTP）必须出事件循环：
    # 否则 perform_checkin 内的 emit_event 自 POST 本进程时，事件循环被阻塞无法
    # 服务该请求 → 互相等待双双超时，时间线事件丢失（打卡响应也卡 ~10s）
    names = await run_in_threadpool(_checkin_or_400, save_uploaded_images, user_id, payloads)
    return await run_in_threadpool(perform_checkin, user_id, names)


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
    return SettingsOut(
        privacy=settings.get("privacy", {}),
        email=settings.get("email"),
        email_bound_at=settings.get("email_bound_at"),
    )


@router.post("/api/me/email/code")
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


@router.post("/api/me/email/bind")
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


@router.post("/api/me/email/unbind")
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
