"""跑团子应用：DND 车卡与角色查看。"""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core import character_store as char_store
from core import user_settings as user_settings_mod
from core.auth import verify_login_key
from core.onebot_client import resolve_avatar_url, resolve_display_name
from core.trpg import character as trpg_char
from core.trpg import rules as trpg_rules

STATIC_DIR = Path(__file__).resolve().parent / "static"
SHARED_STATIC_DIR = Path(__file__).resolve().parent.parent / "core" / "web" / "static"

app = FastAPI(title="BotEro 跑团", version="1.0.0")


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


class LoginIn(BaseModel):
    key: str


class SessionOut(BaseModel):
    user_id: str
    display_name: str
    avatar_url: str
    token: str


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


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "trpg.html")


@app.get("/char/{user_id}/{char_id}")
def trpg_char_view_page(user_id: str, char_id: int):
    page = STATIC_DIR / "char_view.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少角色卡查看页")
    return FileResponse(page)


app.mount("/shared", StaticFiles(directory=SHARED_STATIC_DIR), name="shared")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
