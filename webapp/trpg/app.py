"""跑团子应用：DND 车卡、角色查看与跑团记录浏览。"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core import character_store as char_store
from core import user_settings as user_settings_mod
from core.onebot_client import resolve_display_name
from core.trpg import character as trpg_char
from core.trpg import records as trpg_records
from core.trpg import rules as trpg_rules
from core.web.auth_deps import get_current_user_id
from webapp import STATIC_DIR

router = APIRouter()

MEDIA_URL_PREFIX = "/trpg/media"


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


@router.get("/trpg/char/{user_id}/{char_id}")
def trpg_char_view_page(user_id: str, char_id: int):
    page = STATIC_DIR / "char_view.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少角色卡查看页")
    return FileResponse(page)


# —— 跑团记录（server_data/trpg_records 只读，结构见 core/trpg/records.py）——

def _record_state(record_path: Path, meta: dict) -> str:
    if meta.get("end") is None:
        return "recording"
    return "ended"


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
    return {
        "group_id": group_id,
        "group_name": meta.get("group_name") or "",
        "start": meta.get("start") or "",
        "start_dir": record_path.name,
        "end": meta.get("end"),
        "state": _record_state(record_path, meta),
        "message_count": len(messages),
        "last_message_at": messages[-1].get("time") if messages else None,
        "participants": meta.get("participants") or [],
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
