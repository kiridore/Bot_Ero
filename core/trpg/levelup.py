"""DND 5E 升级：等级判定、HP 增长、属性值提升（ASI）与升级历史。

等级由卡片 `level` 显式保存（不再由 XP 反推）；XP 只决定「够不够升」。
"""

from .rules import ATTRIBUTES, ATTRIBUTE_EN, RACES, XP_THRESHOLDS, ability_modifier, class_info

MAX_LEVEL = 20
ASI_LEVELS = (4, 8, 12, 16, 19)
SCORE_CAP = 20
HP_MODES = {"average": "取均值", "roll": "掷骰"}


def current_level(card: dict) -> int:
    try:
        level = int(card.get("level") or 1)
    except (TypeError, ValueError):
        level = 1
    return max(1, min(level, MAX_LEVEL))


def next_threshold(level: int):
    """升到下一级所需 XP；已满级返回 None。"""
    if level >= MAX_LEVEL:
        return None
    index = min(level, len(XP_THRESHOLDS) - 1)
    return XP_THRESHOLDS[index]


def can_level_up(card: dict) -> bool:
    level = current_level(card)
    threshold = next_threshold(level)
    if threshold is None:
        return False
    return int(card.get("xp") or 0) >= threshold


def asi_required(level: int) -> bool:
    return level + 1 in ASI_LEVELS


def hp_gain(card: dict, mode: str, roll=None) -> int:
    """升级时最大 HP 的增长量：取均值或掷生命骰，均加体质加值。"""
    if mode not in HP_MODES:
        raise ValueError("未知的 HP 增长方式")
    die = class_info(card.get("class_name", "")).get("hp_die", 8)
    con_mod = ability_modifier(int(card.get("con_score") or 10) + RACES.get(card.get("race", ""), {}).get("体质", 0))
    if mode == "average":
        base = die // 2 + 1
    else:
        value = roll if roll is not None else 0
        if not 1 <= int(value) <= die:
            raise ValueError(f"掷骰结果应在 1-{die} 之间")
        base = int(value)
    return max(base + con_mod, 1)


def _score_key(name: str):
    """接受 `str` / `力量` 两种写法。"""
    if name in ATTRIBUTE_EN:
        return ATTRIBUTE_EN[name]
    return name if name in ATTRIBUTE_EN.values() else None


def validate_asi(card: dict, asi: dict) -> dict:
    """校验属性提升分配：单属性 +2 或两项各 +1，最终值（含种族加值）不超过 20。"""
    if not asi:
        raise ValueError("该等级需要分配属性值提升")
    cleaned = {}
    for name, amount in asi.items():
        key = _score_key(str(name))
        if key is None:
            raise ValueError(f"未知属性：{name}")
        try:
            value = int(amount)
        except (TypeError, ValueError):
            raise ValueError("属性提升值必须是整数")
        if value <= 0:
            continue
        cleaned[key] = cleaned.get(key, 0) + value
    if sum(cleaned.values()) != 2:
        raise ValueError("属性值提升共 2 点：一项 +2 或两项各 +1")
    if len(cleaned) > 2:
        raise ValueError("属性值提升最多分配到两项属性")
    bonuses = RACES.get(card.get("race", ""), {})
    for key, amount in cleaned.items():
        attr = next((a for a, en in ATTRIBUTE_EN.items() if en == key), "")
        base = int(card.get(f"{key}_score") or 0)
        if base + bonuses.get(attr, 0) + amount > SCORE_CAP:
            raise ValueError(f"{attr}提升后不能超过 {SCORE_CAP}（当前 {base + bonuses.get(attr, 0)}）")
    return cleaned


def apply_level_up(card: dict, hp_mode: str, asi=None, features_text: str = "", roll=None) -> dict:
    """原地升级并返回结果摘要；不满足条件时抛 ValueError。"""
    level = current_level(card)
    if level >= MAX_LEVEL:
        raise ValueError("已经是 20 级，无法继续升级")
    threshold = next_threshold(level)
    if int(card.get("xp") or 0) < threshold:
        raise ValueError(f"经验值不足：升到 {level + 1} 级需要 {threshold} XP")

    gain = hp_gain(card, hp_mode, roll)
    new_level = level + 1
    if asi_required(level):
        cleaned = validate_asi(card, asi or {})
    else:
        cleaned = {}

    for key, amount in cleaned.items():
        card[f"{key}_score"] = int(card.get(f"{key}_score") or 0) + amount

    card["level"] = new_level
    card["hp"] = int(card.get("hp") or 0) + gain
    card["current_hp"] = int(card.get("current_hp") or 0) + gain
    history = list(card.get("level_history") or [])
    history.append({
        "level": new_level,
        "hp_gain": gain,
        "hp_mode": hp_mode,
        "asi": cleaned,
    })
    card["level_history"] = history
    if features_text.strip():
        existing = (card.get("features") or "").rstrip()
        card["features"] = (existing + "\n" + features_text.strip()) if existing else features_text.strip()
    return {
        "level": new_level,
        "hp_gain": gain,
        "hp": card["hp"],
        "asi": cleaned,
        "asi_required": asi_required(new_level),
        "next_threshold": next_threshold(new_level),
    }


def status(card: dict) -> dict:
    """给网页与机器人用的升级状态。"""
    level = current_level(card)
    threshold = next_threshold(level)
    xp = int(card.get("xp") or 0)
    return {
        "level": level,
        "max_level": MAX_LEVEL,
        "xp": xp,
        "next_threshold": threshold,
        "can_level_up": threshold is not None and xp >= threshold,
        "xp_to_next": max(threshold - xp, 0) if threshold is not None else 0,
        "asi_required": threshold is not None and asi_required(level),
        "hp_die": class_info(card.get("class_name", "")).get("hp_die", 8),
    }
