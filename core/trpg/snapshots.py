"""跑团记录里的角色卡快照：开录存一份、结束时再存一份。

只保留复盘需要的字段，避免把整份卡（含装备长文本、笔记）塞进 meta.json。
"""

from core import character_store as store

from . import character as dnd
from . import coc

MAX_SKILLS = 80


def sheet_snapshot(card: dict) -> dict:
    """按卡片规则压缩出一份角色卡快照。"""
    rules = card.get("rules") or "dnd5e"
    if rules == "coc7th":
        fin = coc.finalize(card)
        skills = {}
        for name, entry in list(fin["skills"].items())[:MAX_SKILLS]:
            skills[name] = entry["total"]
        return {
            "rules": "coc7th",
            "char_name": card.get("char_name", ""),
            "occupation": card.get("occupation", ""),
            "age": card.get("age", 0),
            "scores": dict(fin["scores"]),
            "hp": fin["hp"], "current_hp": fin["current_hp"],
            "mp": fin["mp"], "current_mp": fin["current_mp"],
            "san": fin["san"], "max_san": fin["max_san"], "current_san": fin["current_san"],
            "mov": fin["mov"], "db": fin["db"], "build": fin["build"], "dodge": fin["dodge"],
            "skills": skills,
        }
    fin = dnd.finalize(card)
    return {
        "rules": "dnd5e",
        "char_name": card.get("char_name", ""),
        "race": card.get("race", ""),
        "class_name": card.get("class_name", ""),
        "level": fin["level"], "xp": int(card.get("xp") or 0),
        "scores": dict(fin["scores"]),
        "hp": fin["hp"], "current_hp": int(card.get("current_hp") or fin["hp"]),
        "ac": fin["ac"], "prof_bonus": fin["prof_bonus"],
        "passive_perception": fin["passive_perception"],
        "initiative": fin["initiative"], "hit_dice": fin["hit_dice"],
        "proficient_skills": list(card.get("proficient_skills") or []),
        "saving_profs": list(card.get("saving_profs") or []),
    }


def attach_end_snapshots(meta: dict) -> None:
    """给 meta.participants 补 char_id 与 sheet_end（角色卡已删除时跳过）。"""
    for person in meta.get("participants") or []:
        if not isinstance(person, dict):
            continue
        user_id = str(person.get("user_id") or "")
        char_id = person.get("char_id")
        if not user_id or not char_id:
            continue
        try:
            card = store.get_char(user_id, int(char_id))
        except (TypeError, ValueError):
            card = None
        if not card:
            continue
        person.setdefault("char_id", char_id)
        person["char_name"] = card.get("char_name") or person.get("char_name", "")
        person["sheet_end"] = sheet_snapshot(card)
