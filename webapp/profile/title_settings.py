"""网页端称号装备读写。"""

from __future__ import annotations

from core.database_manager import DbManager

from core.title_defs import TITLE_DEFS
from webapp.profile.title_loader import load_title_module

MAX_EQUIPPED = 3


def _evaluate_unlocks(user_id: str) -> None:
    try:
        mod = load_title_module()
    except RuntimeError:
        return
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
    equipped_ids = db.titles.equipped_all(user_id)
    unlocked_ids = db.titles.list(user_id)
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
    unlocked = set(db.titles.list(user_id))
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
    db.titles.clear_equipped(user_id)
    for tid in ordered:
        ok, reason = db.titles.equip(user_id, tid, max_count=MAX_EQUIPPED)
        if not ok and reason != "already":
            raise ValueError("装备失败，请稍后重试")
    _evaluate_unlocks(user_id)
    return get_title_settings(user_id)


def equip_title(user_id: str, title_id: int) -> dict:
    tid = int(title_id)
    if tid not in TITLE_DEFS:
        raise ValueError("无效称号编号")
    db = DbManager()
    if not db.titles.has(user_id, tid):
        raise ValueError("尚未解锁该称号")
    equipped = db.titles.equipped_all(user_id)
    if tid in equipped:
        return get_title_settings(user_id)
    if len(equipped) >= MAX_EQUIPPED:
        raise ValueError(f"最多装备 {MAX_EQUIPPED} 个称号，请先卸下")
    ok, reason = db.titles.equip(user_id, tid, max_count=MAX_EQUIPPED)
    if not ok and reason == "full":
        raise ValueError(f"最多装备 {MAX_EQUIPPED} 个称号")
    if not ok and reason != "already":
        raise ValueError("装备失败")
    _evaluate_unlocks(user_id)
    return get_title_settings(user_id)


def unequip_title(user_id: str, title_id: int) -> dict:
    tid = int(title_id)
    db = DbManager()
    equipped = db.titles.equipped_all(user_id)
    if tid not in equipped:
        raise ValueError("当前未装备该称号")
    new_ids = [t for t in equipped if t != tid]
    return set_equipped_titles(user_id, new_ids)


def clear_equipped_titles(user_id: str) -> dict:
    db = DbManager()
    db.titles.clear_equipped(user_id)
    _evaluate_unlocks(user_id)
    return get_title_settings(user_id)
