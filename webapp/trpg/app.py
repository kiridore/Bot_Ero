"""跑团子应用：DND 车卡、角色查看与跑团记录浏览。"""

import random
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core import character_store as char_store
from core import user_settings as user_settings_mod
from core.onebot_client import resolve_display_name
from core.trpg import character as trpg_char
from core.trpg import levelup as trpg_levelup
from core.trpg import coc as trpg_coc
from core.trpg import coc_data
from core.trpg import records as trpg_records
from core.trpg import rules as trpg_rules
from core.trpg.game_systems import rule_name
from core.web.auth_deps import get_current_user_id
from webapp import STATIC_DIR

router = APIRouter()

MEDIA_URL_PREFIX = "/trpg/media"


class CharacterIn(BaseModel):
    char_name: str
    rules: str = "dnd5e"
    attributes_mode: str = "manual"
    # COC 7th 专属（DND 卡留空）
    occupation: str = ""
    age: int = 0
    sex: str = ""
    residence: str = ""
    birthplace: str = ""
    era: str = ""
    luck: int = 0
    credit_rating: int = 0
    cthulhu_mythos: int = 0
    san_loss_day: str = ""
    san_loss_today: int = 0
    current_mp: int = 0
    current_san: int = 0
    occupation_choices: dict[str, list[str]] = {}
    skills: dict = {}
    weapons: list[dict] = []
    assets: dict = {}
    social_background: dict = {}
    # DND 5E 专属
    race: str = ""
    class_name: str = ""
    level: int = 1
    background: str = ""
    alignment: str = ""
    xp: int = 0
    str_score: int = 0
    dex_score: int = 0
    con_score: int = 0
    int_score: int = 0
    wis_score: int = 0
    cha_score: int = 0
    # COC 7th 属性（与 DND 共用 str/con/dex/int，其余独立）
    siz_score: int = 0
    app_score: int = 0
    pow_score: int = 0
    edu_score: int = 0
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


class CharOut(BaseModel):
    id: int
    user_id: str
    display_name: str
    char_name: str = ""
    rules: str = "dnd5e"
    notes: str = ""
    # 派生展示（按规则填充）
    hp: int = 0
    ac: int = 0
    scores: dict = {}
    skill_mods: dict = {}
    save_mods: dict = {}
    prof_bonus: int = 0
    passive_perception: int = 0
    initiative: int = 0
    hit_dice: str = ""
    can_level_up: bool = False
    xp_to_next: int = 0
    hp_gain: int = 0
    # 通用
    level: int = 1
    xp: int = 0
    background: str = ""
    alignment: str = ""
    # DND 5E
    race: str = ""
    class_name: str = ""
    str_score: int = 0
    dex_score: int = 0
    con_score: int = 0
    int_score: int = 0
    wis_score: int = 0
    cha_score: int = 0
    # COC 7th 属性（与 DND 共用 str/con/dex/int，其余独立）
    siz_score: int = 0
    app_score: int = 0
    pow_score: int = 0
    edu_score: int = 0
    proficient_skills: list[str] = []
    saving_profs: list[str] = []
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
    # COC 7th
    occupation: str = ""
    age: int = 0
    sex: str = ""
    residence: str = ""
    birthplace: str = ""
    era: str = ""
    luck: int = 0
    credit_rating: int = 0
    cthulhu_mythos: int = 0
    san_loss_day: str = ""
    san_loss_today: int = 0
    current_mp: int = 0
    current_san: int = 0
    occupation_choices: dict[str, list[str]] = {}
    skills: dict = {}
    weapons: list[dict] = []
    assets: dict = {}
    social_background: dict = {}
    mp: int = 0
    san: int = 0
    max_san: int = 0
    current_mp: int = 0
    current_san: int = 0
    mov: int = 0
    db: str = ""
    build: int = 0
    dodge: int = 0
    occupation_info: dict | None = None
    occupation_budget: int = 0
    occupation_spent: int = 0
    interest_budget: int = 0
    interest_spent: int = 0


class LevelUpIn(BaseModel):
    hp_mode: str = "average"
    asi: dict[str, int] = {}
    features: str = ""


def _char_to_out(data: dict) -> CharOut:
    payload = dict(data)
    payload["display_name"] = resolve_display_name(data["user_id"])
    rules = data.get("rules") or "dnd5e"
    payload["rules"] = rules
    if rules == "coc7th":
        fin = trpg_coc.finalize(data)
        for key in ("scores", "hp", "mp", "san", "max_san", "current_hp", "current_mp", "current_san",
                    "mov", "db", "build", "dodge",
                    "skills", "occupation_info", "occupation_budget", "occupation_spent",
                    "interest_budget", "interest_spent"):
            payload[key] = fin[key]
    else:
        fin = trpg_char.finalize(data)
        payload["hp"] = fin["hp"]
        payload["ac"] = fin["ac"]
        for key in ("skill_mods", "scores", "prof_bonus", "save_mods",
                    "passive_perception", "initiative", "hit_dice"):
            payload[key] = fin.get(key, payload.get(key))
        state = trpg_levelup.status(data)
        payload["can_level_up"] = state["can_level_up"]
        payload["xp_to_next"] = state["xp_to_next"]
    return CharOut(**{k: v for k, v in payload.items() if k in CharOut.model_fields})


def _apply_rules(data: dict) -> None:
    """按卡片规则算派生值并校验；非法数据抛 400。"""
    if (data.get("rules") or "dnd5e") == "coc7th":
        problems = trpg_coc.validate(data)
        if problems:
            raise HTTPException(status_code=400, detail="；".join(problems))
        data["hp"] = trpg_coc.finalize(data)["hp"]
        return
    if int(data.get("xp", 0)) <= 0 and int(data.get("level", 1)) > 1:
        data["xp"] = trpg_rules.XP_THRESHOLDS[min(int(data["level"]) - 1, len(trpg_rules.XP_THRESHOLDS) - 1)]
    problems = trpg_char.validate(data)
    if problems:
        raise HTTPException(status_code=400, detail="；".join(problems))
    finalized = trpg_char.finalize(data)
    data["hp"] = finalized["hp"]
    data["ac"] = finalized["ac"]


@router.get("/api/trpg/coc/options")
def api_coc_options():
    """建卡工具的数据源：技能基础值、职业模板与类别。"""
    return {
        "skill_base": trpg_coc.SKILL_BASE,
        "skill_categories": list(trpg_coc.SKILL_CATEGORIES),
        "skill_aliases": dict(trpg_coc.SKILL_ALIASES),
        "occupations": [
            {"seq": seq, "name": name, "credit_min": low, "credit_max": high,
             "formula": formula, "own_skills": own}
            for seq, name, low, high, formula, own in trpg_coc.OCCUPATIONS
            if seq >= 1  # seq 0 是 xlsx 里的工具说明行，不是职业
        ],
        "occupation_skills": coc_data.OCCUPATION_SKILLS,
    }


@router.get("/api/me/characters")
def api_my_characters(user_id: Annotated[str, Depends(get_current_user_id)]):
    chars = char_store.list_chars(user_id)
    current = char_store.get_current(user_id)
    current_id = current["id"] if current else None
    return {
        "current_id": current_id,
        "characters": [_char_to_out(c) for c in chars],
    }


@router.post("/api/me/characters", response_model=CharOut)
def api_create_character(
    body: CharacterIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    data = body.model_dump()
    _apply_rules(data)
    if data.get("rules") == "coc7th":
        # 新建 COC 卡：当前值未填时按上限初始化，避免存成 0
        fin = trpg_coc.finalize(data)
        for key, cap in (("current_hp", "hp"), ("current_mp", "mp"), ("current_san", "san")):
            if not data.get(key):
                data[key] = fin[cap]
    try:
        char_id = char_store.create_char(user_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _char_to_out(char_store.get_char(user_id, char_id))


@router.get("/api/me/characters/{char_id}", response_model=CharOut)
def api_get_my_character(
    char_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    char = char_store.get_char(user_id, char_id)
    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")
    return _char_to_out(char)


@router.put("/api/me/characters/{char_id}", response_model=CharOut)
def api_update_character(
    char_id: int,
    body: CharacterIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    if not char_store.get_char(user_id, char_id):
        raise HTTPException(status_code=404, detail="角色不存在")
    data = body.model_dump()
    _apply_rules(data)
    try:
        char_store.update_char(user_id, char_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _char_to_out(char_store.get_char(user_id, char_id))


@router.post("/api/me/characters/{char_id}/levelup", response_model=CharOut)
def api_level_up(
    char_id: int,
    body: LevelUpIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    char = char_store.get_char(user_id, char_id)
    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")
    if (char.get("rules") or "dnd5e") != "dnd5e":
        raise HTTPException(status_code=400, detail="升级向导只适用于 DND 5E 角色卡")
    roll = random.randint(1, trpg_levelup.status(char)["hp_die"]) if body.hp_mode == "roll" else None
    try:
        result = trpg_levelup.apply_level_up(
            char, body.hp_mode, body.asi, body.features, roll=roll)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    char_store.update_char(user_id, char_id, char)
    out = _char_to_out(char_store.get_char(user_id, char_id))
    out.hp_gain = result["hp_gain"]
    return out


@router.delete("/api/me/characters/{char_id}")
def api_delete_character(
    char_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    if not char_store.get_char(user_id, char_id):
        raise HTTPException(status_code=404, detail="角色不存在")
    char_store.delete_char(user_id, char_id)
    return {"ok": True}


@router.post("/api/me/characters/{char_id}/activate")
def api_activate_character(
    char_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    try:
        char_store.set_current(user_id, char_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


@router.get("/api/characters/{user_id}/{char_id}", response_model=CharOut)
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


@router.get("/api/trpg/rules")
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
        "attribute_modes": trpg_rules.ATTRIBUTE_MODES,
        "alignments": {
            "law": ["守序", "中立", "混乱"],
            "moral": ["善良", "中立", "邪恶"],
        },
    }


@router.get("/trpg")
def trpg_page():
    page = STATIC_DIR / "trpg.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少静态页面")
    return FileResponse(page)


@router.get("/trpg/levelup/{char_id}")
def trpg_levelup_page(char_id: int):
    page = STATIC_DIR / "trpg_levelup.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少升级向导页")
    return FileResponse(page)


@router.get("/trpg/char/{user_id}/{char_id}")
def trpg_char_view_page(user_id: str, char_id: int):
    page = STATIC_DIR / "char_view.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少角色卡查看页")
    return FileResponse(page)


# —— 跑团记录（server_data/trpg_records 只读，结构见 core/trpg/records.py）——

def _record_state(record_path: Path, meta: dict) -> str:
    return "recording" if meta.get("end") is None else "ended"


def _my_role(participants, user_id) -> dict:
    """登录用户在本场记录里的身份：dm / ob / player（附角色卡名），未参与为空。"""
    for person in participants:
        if not isinstance(person, dict) or str(person.get("user_id")) != str(user_id):
            continue
        role = person.get("role") or "player"
        return {"role": role, "char_name": person.get("char_name") or ""}
    return {"role": "", "char_name": ""}


def _segment_with_url(segment, group_id: str, start_dir: str):
    if not isinstance(segment, dict) or segment.get("type") != "image":
        return segment
    seg = dict(segment)
    try:
        name = trpg_records.media_file(group_id, start_dir, Path(str(seg.get("local") or "")).name).name
    except ValueError:
        return seg  # 下载失败或路径异常的分段只保留 unavailable 标记
    seg["url"] = f"{MEDIA_URL_PREFIX}/{group_id}/{start_dir}/{name}"
    return seg


def _summary(group_id: str, record_path: Path):
    try:
        trpg_records.record_dir(group_id, record_path.name)
    except ValueError:
        return None
    meta = trpg_records.read_meta(record_path)
    if not meta or meta.get("version") != 2:
        return None
    if not (record_path / "messages.jsonl").is_file():
        return None
    # shortcut: 列表为拿条数与最后时间整读 messages.jsonl，记录数上千时改由写入方把计数写进 meta.json
    messages, _skipped = trpg_records.iter_messages(record_path)
    participants = meta.get("participants") or []
    return {
        "group_id": group_id,
        "group_name": meta.get("group_name") or "",
        "start": meta.get("start") or "",
        "start_dir": record_path.name,
        "end": meta.get("end"),
        "state": _record_state(record_path, meta),
        "rules": meta.get("rules") or "",
        "rules_name": rule_name(meta["rules"]) if meta.get("rules") else "未知规则",
        "player_count": sum(1 for p in participants if isinstance(p, dict) and not p.get("role")),
        "message_count": len(messages),
        "last_message_at": messages[-1].get("time") if messages else None,
        "participants": participants,
    }


def _require_record(group_id: str, start_dir: str) -> Path:
    try:
        record_path = trpg_records.record_dir(group_id, start_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    meta = trpg_records.read_meta(record_path)
    if not meta or meta.get("version") != 2 or not (record_path / "messages.jsonl").is_file():
        raise HTTPException(status_code=404, detail="记录不存在")
    return record_path


@router.get("/api/trpg/records")
def api_trpg_records(
    user_id: Annotated[str, Depends(get_current_user_id)],
    mine: int = 0,
):
    items = []
    root = trpg_records.records_root()
    if root.is_dir():
        for group_path in root.iterdir():
            if not group_path.is_dir():
                continue
            for record_path in group_path.iterdir():
                if not record_path.is_dir():
                    continue
                item = _summary(group_path.name, record_path)
                if item is None:
                    continue
                item["is_mine"] = any(
                    str(p.get("user_id")) == str(user_id) for p in item["participants"] if isinstance(p, dict)
                )
                item["my_role"] = _my_role(item["participants"], user_id)
                if mine and not item["is_mine"]:
                    continue
                items.append(item)
    items.sort(key=lambda it: it["start_dir"], reverse=True)
    return {"records": items}


@router.get("/api/trpg/records/{group_id}/{start_dir}")
def api_trpg_record(
    group_id: str,
    start_dir: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    start_from: int = Query(0, ge=0, alias="from"),
    reveal: int = 0,
):
    record_path = _require_record(group_id, start_dir)
    meta = trpg_records.read_meta(record_path) or {}
    messages, _skipped = trpg_records.iter_messages(record_path)
    total = len(messages)
    window = messages[start_from:] if start_from < total else []
    # 暗骰默认过滤但仍计入 total：客户端用 total 作为下一次 from，增量索引不漂移
    visible = window if reveal else [m for m in window if not m.get("secret")]
    return {
        "group_id": group_id,
        "group_name": meta.get("group_name") or "",
        "start": meta.get("start") or "",
        "end": meta.get("end"),
        "state": _record_state(record_path, meta),
        "rules": meta.get("rules") or "",
        "rules_name": rule_name(meta["rules"]) if meta.get("rules") else "未知规则",
        "participants": meta.get("participants") or [],
        "total": total,
        "from": start_from,
        "messages": [
            {
                **entry,
                "segments": [_segment_with_url(seg, group_id, start_dir) for seg in entry["segments"]],
            }
            for entry in visible
        ],
    }


@router.get("/trpg/media/{group_id}/{start_dir}/{filename}")
def trpg_record_media(
    group_id: str,
    start_dir: str,
    filename: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    try:
        path = trpg_records.media_file(group_id, start_dir, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(path)


@router.get("/trpg/coc")
@router.get("/trpg/coc/{char_id}")
def trpg_coc_page(char_id: int | None = None):
    page = STATIC_DIR / "trpg_coc.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少 COC 建卡页面")
    return FileResponse(page)


@router.get("/trpg/records")
def trpg_records_page():
    page = STATIC_DIR / "trpg_records.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少静态页面")
    return FileResponse(page)


@router.get("/trpg/records/{group_id}/{start_dir}")
def trpg_record_page(group_id: str, start_dir: str):
    page = STATIC_DIR / "trpg_record.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少静态页面")
    return FileResponse(page)
