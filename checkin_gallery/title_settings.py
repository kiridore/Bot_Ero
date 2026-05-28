"""网页端称号装备读写。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from core.database_manager import DbManager

from checkin_gallery.profile_service import TITLE_DEFS

MAX_EQUIPPED = 3
_TITLE_MODULE_PATH = Path(__file__).resolve().parent.parent / "plugins" / "title.py"


def _evaluate_unlocks(user_id: str) -> None:
    spec = importlib.util.spec_from_file_location("botero_title_eval", _TITLE_MODULE_PATH)
    if spec is None or spec.loader is None:
        return
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = getattr(mod, "evaluate_and_unlock_titles", None)
    if fn:
        fn(DbManager(), user_id)


def _title_brief(tid: int) -> dict:
    data = TITLE_DEFS.get(tid, {})
    return {
        "id": tid,
        "name": data.get("name", "未知称号"),
        "rarity": data.get("rarity", "unknown"),
        "description": data.get("description", ""),
    }


def get_title_settings(user_id: str) -> dict:
    db = DbManager()
    equipped_ids = db.get_equipped_titles(user_id)
    unlocked_ids = db.get_user_titles(user_id)
    equipped_set = set(equipped_ids)

    equipped = []
    for slot, tid in enumerate(equipped_ids, start=1):
        item = _title_brief(tid)
        item["slot"] = slot
        equipped.append(item)

    unlocked = []
    for tid in sorted(unlocked_ids):
        if tid not in TITLE_DEFS:
            continue
        item = _title_brief(tid)
        item["equipped"] = tid in equipped_set
        unlocked.append(item)

    prefix = "·".join(item["name"] for item in equipped)
    display_prefix = f"「{prefix}」" if prefix else ""

    return {
        "max_equipped": MAX_EQUIPPED,
        "equipped": equipped,
        "unlocked": unlocked,
        "display_prefix": display_prefix,
    }


def _validate_title_ids(user_id: str, title_ids: list[int]) -> list[int]:
    if len(title_ids) > MAX_EQUIPPED:
        raise ValueError(f"最多装备 {MAX_EQUIPPED} 个称号")
    if len(title_ids) != len(set(title_ids)):
        raise ValueError("不能重复装备同一称号")

    db = DbManager()
    unlocked = set(db.get_user_titles(user_id))
    cleaned: list[int] = []
    for raw in title_ids:
        tid = int(raw)
        if tid not in TITLE_DEFS:
            raise ValueError(f"无效称号编号：{tid}")
        if tid not in unlocked:
            raise ValueError(f"尚未解锁称号：{tid}")
        cleaned.append(tid)
    return cleaned


def set_equipped_titles(user_id: str, title_ids: list[int]) -> dict:
    ordered = _validate_title_ids(user_id, title_ids)
    db = DbManager()
    db.clear_equipped_titles(user_id)
    for tid in ordered:
        ok, reason = db.equip_title(user_id, tid, max_count=MAX_EQUIPPED)
        if not ok and reason != "already":
            raise ValueError("装备失败，请稍后重试")
    _evaluate_unlocks(user_id)
    return get_title_settings(user_id)


def equip_title(user_id: str, title_id: int) -> dict:
    tid = int(title_id)
    if tid not in TITLE_DEFS:
        raise ValueError("无效称号编号")
    db = DbManager()
    if not db.has_title(user_id, tid):
        raise ValueError("尚未解锁该称号")
    equipped = db.get_equipped_titles(user_id)
    if tid in equipped:
        return get_title_settings(user_id)
    if len(equipped) >= MAX_EQUIPPED:
        raise ValueError(f"最多装备 {MAX_EQUIPPED} 个称号，请先卸下")
    ok, reason = db.equip_title(user_id, tid, max_count=MAX_EQUIPPED)
    if not ok and reason == "full":
        raise ValueError(f"最多装备 {MAX_EQUIPPED} 个称号")
    if not ok and reason != "already":
        raise ValueError("装备失败")
    _evaluate_unlocks(user_id)
    return get_title_settings(user_id)


def unequip_title(user_id: str, title_id: int) -> dict:
    tid = int(title_id)
    db = DbManager()
    equipped = db.get_equipped_titles(user_id)
    if tid not in equipped:
        raise ValueError("当前未装备该称号")
    new_ids = [t for t in equipped if t != tid]
    return set_equipped_titles(user_id, new_ids)


def clear_equipped_titles(user_id: str) -> dict:
    db = DbManager()
    db.clear_equipped_titles(user_id)
    _evaluate_unlocks(user_id)
    return get_title_settings(user_id)
