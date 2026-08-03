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
from checkin_gallery.guestbook_service import like_entry, list_entries, post_entry
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
from core import character_store as char_store
from core import user_settings as user_settings_mod
from core.trpg import character as trpg_char
from core.trpg import rules as trpg_rules

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


class GuestbookPostIn(BaseModel):
    content: str


class CharacterIn(BaseModel):
    char_name: str
    race: str
    class_name: str
    level: int = 1
    background: str = ""
    alignment: str = ""
    xp: int = 0
    str_score: int
    dex_score: int
    con_score: int
    int_score: int
    wis_score: int
    cha_score: int
    proficient_skills: list[str] = []
    saving_profs: list[str] = []
    hp: int = 0
    ac: int = 0
    current_hp: int = 0
    temp_hp: int = 0
    speed: int = 30
    death_saves_success: int = 0
    death_saves_fail: int = 0
    inspiration: bool = False
    equipment: list[str] = []
    other_proficiencies: str = ""
    attacks: list[str] = []
    features: str = ""
    personality_traits: str = ""
    ideals: str = ""
    bonds: str = ""
    flaws: str = ""
    notes: str = ""


class SettingsIn(BaseModel):
    privacy: dict | None = None


class SettingsOut(BaseModel):
    privacy: dict


class CharOut(BaseModel):
    id: int
    user_id: str
    display_name: str
    char_name: str
    race: str
    class_name: str
    level: int
    hp: int
    ac: int
    skill_mods: dict
    scores: dict
    prof_bonus: int
    save_mods: dict
    passive_perception: int
    initiative: int
    hit_dice: str
    proficient_skills: list[str]
    notes: str
    background: str
    alignment: str
    xp: int
    str_score: int
    dex_score: int
    con_score: int
    int_score: int
    wis_score: int
    cha_score: int
    saving_profs: list[str]
    current_hp: int
    temp_hp: int
    speed: int
    death_saves_success: int
    death_saves_fail: int
    inspiration: bool
    equipment: list[str]
    other_proficiencies: str
    attacks: list[str]
    features: str
    personality_traits: str
    ideals: str
    bonds: str
    flaws: str


def _char_to_out(data: dict) -> CharOut:
    base_scores = {k: data.get(k, 8) for k in (
        "str_score", "dex_score", "con_score", "int_score", "wis_score", "cha_score"
    )}
    finalized = trpg_char.finalize(data)
    return CharOut(
        id=data["id"],
        user_id=data["user_id"],
        display_name=resolve_display_name(data["user_id"]),
        char_name=finalized["char_name"],
        race=finalized.get("race", ""),
        class_name=finalized.get("class_name", ""),
        level=int(finalized.get("level", 1)),
        hp=finalized["hp"],
        ac=finalized["ac"],
        skill_mods=finalized.get("skill_mods", {}),
        scores=finalized.get("scores", {}),
        prof_bonus=finalized.get("prof_bonus", 2),
        save_mods=finalized.get("save_mods", {}),
        passive_perception=finalized.get("passive_perception", 10),
        initiative=finalized.get("initiative", 0),
        hit_dice=finalized.get("hit_dice", "1d8"),
        proficient_skills=finalized.get("proficient_skills", []),
        notes=finalized.get("notes", ""),
        background=data.get("background", ""),
        alignment=data.get("alignment", ""),
        xp=int(data.get("xp", 0)),
        str_score=base_scores["str_score"],
        dex_score=base_scores["dex_score"],
        con_score=base_scores["con_score"],
        int_score=base_scores["int_score"],
        wis_score=base_scores["wis_score"],
        cha_score=base_scores["cha_score"],
        saving_profs=data.get("saving_profs", []) or [],
        current_hp=int(data.get("current_hp", 0)),
        temp_hp=int(data.get("temp_hp", 0)),
        speed=int(data.get("speed", 30)),
        death_saves_success=int(data.get("death_saves_success", 0)),
        death_saves_fail=int(data.get("death_saves_fail", 0)),
        inspiration=bool(data.get("inspiration", False)),
        equipment=data.get("equipment", []) or [],
        other_proficiencies=data.get("other_proficiencies", ""),
        attacks=data.get("attacks", []) or [],
        features=data.get("features", ""),
        personality_traits=data.get("personality_traits", ""),
        ideals=data.get("ideals", ""),
        bonds=data.get("bonds", ""),
        flaws=data.get("flaws", ""),
    )


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


def get_optional_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return verify_login_key(authorization[7:].strip())


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


@app.get("/api/guestbook")
def api_guestbook_list(
    viewer_id: Annotated[str | None, Depends(get_optional_user_id)],
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
):
    return list_entries(viewer_id, page, page_size)


@app.post("/api/guestbook")
def api_guestbook_post(
    body: GuestbookPostIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _checkin_or_400(post_entry, user_id, body.content)


@app.post("/api/guestbook/{entry_id}/like")
def api_guestbook_like(
    entry_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _checkin_or_400(like_entry, user_id, entry_id)


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


@app.get("/api/me/characters")
def api_my_characters(user_id: Annotated[str, Depends(get_current_user_id)]):
    chars = char_store.list_chars(user_id)
    current = char_store.get_current(user_id)
    current_id = current["id"] if current else None
    return {
        "current_id": current_id,
        "characters": [_char_to_out(c) for c in chars],
    }


@app.post("/api/me/characters", response_model=CharOut)
def api_create_character(
    body: CharacterIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    data = body.model_dump()
    if int(data.get("xp", 0)) <= 0 and int(data.get("level", 1)) > 1:
        data["xp"] = trpg_rules.XP_THRESHOLDS[min(int(data["level"]) - 1, len(trpg_rules.XP_THRESHOLDS) - 1)]
    finalized = trpg_char.finalize(data)
    data["hp"] = finalized["hp"]
    data["ac"] = finalized["ac"]
    try:
        char_id = char_store.create_char(user_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _char_to_out(char_store.get_char(user_id, char_id))


@app.get("/api/me/characters/{char_id}", response_model=CharOut)
def api_get_my_character(
    char_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    char = char_store.get_char(user_id, char_id)
    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")
    return _char_to_out(char)


@app.put("/api/me/characters/{char_id}", response_model=CharOut)
def api_update_character(
    char_id: int,
    body: CharacterIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    if not char_store.get_char(user_id, char_id):
        raise HTTPException(status_code=404, detail="角色不存在")
    data = body.model_dump()
    if int(data.get("xp", 0)) <= 0 and int(data.get("level", 1)) > 1:
        data["xp"] = trpg_rules.XP_THRESHOLDS[min(int(data["level"]) - 1, len(trpg_rules.XP_THRESHOLDS) - 1)]
    finalized = trpg_char.finalize(data)
    data["hp"] = finalized["hp"]
    data["ac"] = finalized["ac"]
    try:
        char_store.update_char(user_id, char_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _char_to_out(char_store.get_char(user_id, char_id))


@app.delete("/api/me/characters/{char_id}")
def api_delete_character(
    char_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    if not char_store.get_char(user_id, char_id):
        raise HTTPException(status_code=404, detail="角色不存在")
    char_store.delete_char(user_id, char_id)
    return {"ok": True}


@app.post("/api/me/characters/{char_id}/activate")
def api_activate_character(
    char_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    try:
        char_store.set_current(user_id, char_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


@app.get("/api/characters/{user_id}/{char_id}", response_model=CharOut)
def api_view_character(
    user_id: str,
    char_id: int,
    viewer_id: Annotated[str, Depends(get_current_user_id)],
):
    if not str(user_id).isdigit():
        raise HTTPException(status_code=400, detail="非法用户 ID")
    if str(viewer_id) != str(user_id) and not user_settings_mod.privacy_public(user_id):
        raise HTTPException(status_code=403, detail="对方未公开角色卡")
    try:
        char = char_store.get_char(user_id, char_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")
    return _char_to_out(char)


@app.get("/api/trpg/rules")
def api_trpg_rules():
    return {
        "attributes": trpg_rules.ATTRIBUTES,
        "attribute_en": trpg_rules.ATTRIBUTE_EN,
        "skills": trpg_rules.SKILLS,
        "skill_aliases": trpg_rules.SKILL_ALIASES,
        "races": trpg_rules.RACES,
        "classes": trpg_rules.CLASSES,
        "point_buy_cost": trpg_rules.POINT_BUY_COST,
        "point_buy_budget": trpg_rules.POINT_BUY_BUDGET,
        "standard_array": trpg_rules.STANDARD_ARRAY,
        "xp_thresholds": trpg_rules.XP_THRESHOLDS,
        "alignments": {
            "law": ["守序", "中立", "混乱"],
            "moral": ["善良", "中立", "邪恶"],
        },
    }


@app.get("/api/me/settings", response_model=SettingsOut)
def api_my_settings(user_id: Annotated[str, Depends(get_current_user_id)]):
    settings = user_settings_mod.get_settings(user_id)
    return SettingsOut(privacy=settings.get("privacy", {}))


@app.put("/api/me/settings", response_model=SettingsOut)
def api_update_settings(
    body: SettingsIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    patch = body.model_dump(exclude_none=True)
    merged = user_settings_mod.update_settings(user_id, patch)
    return SettingsOut(privacy=merged.get("privacy", {}))


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


@app.get("/guestbook")
def guestbook_page():
    page = STATIC_DIR / "guestbook.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少留言簿页")
    return FileResponse(page)


@app.get("/profile/trpg")
def profile_trpg_page():
    page = STATIC_DIR / "trpg.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少跑团车卡页")
    return FileResponse(page)


@app.get("/trpg/char/{user_id}/{char_id}")
def trpg_char_view_page(user_id: str, char_id: int):
    page = STATIC_DIR / "char_view.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少角色卡查看页")
    return FileResponse(page)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
