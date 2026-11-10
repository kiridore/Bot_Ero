import json

from .rules import (
    ATTRIBUTES,
    CLASSES,
    POINT_BUY_BUDGET,
    POINT_BUY_COST,
    RACES,
    SKILLS,
    STANDARD_ARRAY,
    XP_THRESHOLDS,
    ability_modifier,
    class_info,
    race_bonuses,
)

VALID_MODES = ("point_buy", "rolled", "array", "manual")


def level_from_xp(xp: int) -> int:
    """由经验值反推等级（1-20）。"""
    level = 1
    for i, threshold in enumerate(XP_THRESHOLDS, start=1):
        if xp >= threshold:
            level = i
    return level


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

    xp = int(char_data.get("xp", 0))
    level = level_from_xp(xp) if xp > 0 else int(char_data.get("level", 1))
    out["level"] = level
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


def _base_scores(char_data: dict) -> dict:
    return {attr: int(char_data.get(_attr_key(attr), 0) or 0) for attr in ATTRIBUTES}


def point_buy_spent(char_data: dict) -> int:
    return sum(POINT_BUY_COST.get(value, 99) for value in _base_scores(char_data).values())


def suggest_hp(char_data: dict) -> int:
    """按 5E 规则算 HP：1 级取满骰，之后每级取骰面均值（向上取整）加上体质加值。"""
    fin = finalize(char_data)
    level = max(int(fin.get("level") or 1), 1)
    die = class_info(char_data.get("class_name", "")).get("hp_die", 8)
    con_mod = ability_modifier(fin["scores"]["con_score"])
    average = die // 2 + 1
    return max(die + con_mod + (level - 1) * (average + con_mod), 1)


def validate(char_data: dict) -> list[str]:
    """建卡校验：属性生成方式对应的取值范围、购点预算、技能选择与豁免数量。"""
    problems = []
    mode = char_data.get("attributes_mode") or "manual"
    if mode not in VALID_MODES:
        problems.append(f"未知的属性生成方式：{mode}")
        mode = "manual"
    base = _base_scores(char_data)
    for attr, value in base.items():
        if mode == "point_buy" and value not in POINT_BUY_COST:
            problems.append(f"{attr}购点值需在 8-15（当前 {value}）")
        elif mode == "rolled" and not 3 <= value <= 18:
            problems.append(f"{attr}掷骰结果应在 3-18（当前 {value}）")
        elif mode == "array" and value not in STANDARD_ARRAY:
            problems.append(f"{attr}应取自标准数组 {STANDARD_ARRAY}（当前 {value}）")
        elif mode == "manual" and not 1 <= value <= 30:
            problems.append(f"{attr}应在 1-30（当前 {value}）")
    if mode == "point_buy":
        spent = point_buy_spent(char_data)
        if spent > POINT_BUY_BUDGET:
            problems.append(f"购点超出预算（{spent}/{POINT_BUY_BUDGET}）")

    race = char_data.get("race") or ""
    if race and race not in RACES:
        problems.append(f"未知种族：{race}")
    class_name = char_data.get("class_name") or ""
    info = CLASSES.get(class_name)
    if class_name and info is None:
        problems.append(f"未知职业：{class_name}")

    chosen = [skill for skill in (char_data.get("proficient_skills") or []) if skill]
    unknown = [skill for skill in chosen if skill not in SKILLS]
    if unknown:
        problems.append("未知技能：" + "、".join(unknown))
    if info:
        allowed = info.get("skills")
        if allowed != "any":
            outside = [skill for skill in chosen if skill not in (allowed or [])]
            if outside:
                problems.append(f"{class_name}不可选技能：" + "、".join(outside))
        if len(chosen) > info.get("skill_count", 0):
            problems.append(f"{class_name}最多选 {info['skill_count']} 项技能（已选 {len(chosen)}）")

    saves = [item for item in (char_data.get("saving_profs") or []) if item in ATTRIBUTES]
    if len(saves) > 2:
        problems.append(f"豁免熟练最多 2 项（已选 {len(saves)}）")
    return problems
