import json

from .rules import (
    ATTRIBUTES,
    SKILLS,
    ability_modifier,
    class_info,
    race_bonuses,
)


def finalize(char_data: dict) -> dict:
    """根据基础属性+种族加值计算最终属性、HP、AC、技能加值。

    返回新增计算字段的副本。
    """
    out = dict(char_data)
    race = char_data.get("race", "")
    bonuses = race_bonuses(race)

    scores = {}
    for attr in ATTRIBUTES:
        key = _attr_key(attr)
        base = int(char_data.get(key, 8))
        scores[key] = base + bonuses.get(attr, 0)
        out[key] = scores[key]
    out["scores"] = scores

    con_mod = ability_modifier(scores["con_score"])
    dex_mod = ability_modifier(scores["dex_score"])

    cls = class_info(char_data.get("class_name", ""))
    hp_die = cls.get("hp_die", 8)
    out["hp"] = hp_die + con_mod if char_data.get("hp") in (None, 0) else int(char_data["hp"])
    out["ac"] = 10 + dex_mod if char_data.get("ac") in (None, 0) else int(char_data["ac"])

    level = int(char_data.get("level", 1))
    out["prof_bonus"] = 2 + (level - 1) // 4

    saving_profs = set(char_data.get("saving_profs", []) or [])
    save_mods = {}
    for attr in ATTRIBUTES:
        mod = ability_modifier(scores[_attr_key(attr)])
        if attr in saving_profs:
            mod += out["prof_bonus"]
        save_mods[attr] = mod
    out["save_mods"] = save_mods

    # 技能加值
    proficient = set(char_data.get("proficient_skills", []) or [])
    skill_mods = {}
    for skill in SKILLS:
        attr = SKILLS[skill]
        mod = ability_modifier(scores[_attr_key(attr)])
        if skill in proficient:
            mod += 2
        skill_mods[skill] = mod
    out["skill_mods"] = skill_mods

    wis_mod = ability_modifier(scores["wis_score"])
    perception_bonus = 2 if "察觉" in proficient else 0
    out["passive_perception"] = 10 + wis_mod + perception_bonus
    out["initiative"] = dex_mod
    out["hit_dice"] = f"{level}d{hp_die}"

    return out


def get_attr_value(char_data: dict, name: str) -> int | None:
    """按中文属性名/技能名取加值（供骰子引用）。"""
    if not char_data:
        return None
    data = finalize(char_data)
    if name in ATTRIBUTES:
        return ability_modifier(data[_attr_key(name)])
    if name in SKILLS:
        return data["skill_mods"].get(name)
    return None


def resolve_expression_values(char_data: dict) -> dict:
    """返回 {属性名/技能名: 加值} 映射（一次 finalize，供骰子表达式替换）。"""
    data = finalize(char_data)
    out = {}
    for attr in ATTRIBUTES:
        out[attr] = ability_modifier(data[_attr_key(attr)])
    out.update(data["skill_mods"])
    return out


def format_sheet(char_data: dict) -> str:
    """格式化角色卡文本（精简视图）。"""
    data = finalize(char_data)
    cls = class_info(data.get("class_name", ""))

    mods = []
    for attr in ATTRIBUTES:
        key = _attr_key(attr)
        mod = ability_modifier(data[key])
        mod_str = f"+{mod}" if mod >= 0 else str(mod)
        mods.append(f"{attr}{mod_str}")
    attr_line = "  ".join(mods)

    lines = [
        f"【{data['char_name']}】 Lv.{data.get('level', 1)} {data.get('race', '?')} {data.get('class_name', '?')}",
        f"HP: {data['hp']}    AC: {data['ac']}    HP骰: d{cls.get('hp_die', 8)}",
        f"属性: {attr_line}",
    ]

    prof_bonus = data.get("prof_bonus", 0)
    init = data.get("initiative", 0)
    passive = data.get("passive_perception", 10)
    hit_dice = data.get("hit_dice", "1d8")
    lines.append(f"熟练加值: +{prof_bonus}    先攻: {init}    被动感知: {passive}    生命骰: {hit_dice}")

    proficient = data.get("proficient_skills", [])
    if proficient:
        lines.append(f"熟练技能: {', '.join(proficient)}")

    notes = data.get("notes", "")
    if notes:
        lines.append(f"备注: {notes}")

    return "\n".join(lines)


def _attr_key(attr: str) -> str:
    mapping = {"力量": "str_score", "敏捷": "dex_score", "体质": "con_score",
               "智力": "int_score", "感知": "wis_score", "魅力": "cha_score"}
    return mapping.get(attr, "")
