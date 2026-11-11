"""COC 7th 幕间成长：技能成长标记与成长检定。

规则（守密人核心规则书 5.11）：成功使用技能得成长标记；幕间为每个打了勾的技能
掷 1D100，结果大于当前技能值或大于 95 则该技能 +1D10（可超过 100%），结算后清空标记；
有技能达到 90% 或更高时当前 SAN 加 2D6。
"""

import random

from .coc import canonical_skill, finalize, skill_total
from .vitals import clamp

SAN_REWARD_SKILL = 90
FUMBLE_SAFE_ROLL = 95


def improves(roll: int, value: int) -> bool:
    """成长检定是否通过：高于当前技能值，或掷出 96-100。"""
    return roll > value or roll > FUMBLE_SAFE_ROLL


def _resolve_key(skills: dict, name: str) -> str | None:
    """卡片里可能用「侦查」而规则表用「侦察」，按别名与前缀回退到实际存在的键。"""
    if name in skills:
        return name
    canon = canonical_skill(name)
    for key in skills:
        if canonical_skill(key) == canon or key.startswith(name) or name.startswith(key):
            return key
    return None


def mark(card: dict, name: str) -> bool:
    """给技能打成长标记；未知技能返回 False。"""
    skills = card.setdefault("skills", {})
    key = _resolve_key(skills, name)
    if key is None:
        return False
    skills[key]["check"] = True
    return True


def checked_skills(card: dict) -> list[str]:
    return [name for name, entry in (card.get("skills") or {}).items() if entry.get("check")]


def settle(card: dict):
    """结算一次幕间成长，原地修改 card。

    返回 (结算明细, SAN 变化)。明细为 [(技能, 成长前, 检定骰, 增长, 成长后), ...]。
    """
    skills = card.setdefault("skills", {})
    details = []
    for name in checked_skills(card):
        entry = skills[name]
        before = skill_total(entry)
        roll = random.randint(1, 100)
        gain = random.randint(1, 10) if improves(roll, before) else 0
        if gain:
            entry["growth"] = int(entry.get("growth") or 0) + gain
        details.append((name, before, roll, gain, skill_total(entry)))
    for entry in skills.values():
        entry["check"] = False

    san_change = 0
    if any(entry["total"] >= SAN_REWARD_SKILL for entry in finalize(card)["skills"].values()):
        san_change = sum(random.randint(1, 6) for _ in range(2))
        if san_change:
            fin = finalize(card)
            card["current_san"] = clamp(int(card.get("current_san") or fin["current_san"]) + san_change,
                                        fin["max_san"])
    return details, san_change
