"""COC 7th 角色卡：派生值、技能点预算与人物卡文本。

建卡逻辑对齐 docs/COC七版人物卡v1.6.1.xlsx：属性手填/掷骰，年龄按守密人核心规则书的建卡调整表
（体能合计扣减由玩家分配、APP 扣减、EDU 成长检定、MOV 每十年 −1），
技能 = 基础值 + 成长 + 职业点 + 兴趣点（上限 99），职业点预算按职业公式、兴趣点 = 智力×2，
信用评级受职业区间约束。伤害加值与体格按 STR+SIZ 查表。
"""

from __future__ import annotations

import random
import re
import time

from core.trpg.coc_data import OCCUPATION_SKILLS, OCCUPATIONS, SKILL_BASE, SKILL_CATEGORIES

SKILL_MAX = 99
SKILL_CEILING = 199  # 幕间成长可使技能超过 100%

# 武器表：文本字段保留原表自由度，但校验可解析性与基础范围
WEAPON_ROWS_MAX = 50
WEAPON_NAME_MAX = 30
WEAPON_TEXT_MAX = {"type": 10, "skill": 20, "range": 20, "ammo": 10, "attacks": 12, "pierce": 10}
WEAPON_FIELD_LABEL = {"type": "类型", "skill": "使用技能", "range": "射程", "ammo": "装弹量",
                      "attacks": "次数", "pierce": "贯穿"}
DICE_TERM_RE = re.compile(r"^(\d{0,2})[dD](\d{1,3})$")
# 次数：1、1(3)、1/2（每两轮一次）、1 or 2、1(2)or连射、全自动、布置
ATTACKS_RE = re.compile(r"^\d{1,2}(\s*\(\d{1,2}\))?(\s*[/or]\s*\d{1,2}|\s*or\s*[^\s]{1,6})*$")
ATTACKS_TEXT_OK = ("全自动", "布置", "一次使用", "N/A")
DASHES = ("", "—", "-", "–", "－")


# xlsx 技能名与规则书常用译名的对应（玩家按习惯输入都能对上）
SKILL_ALIASES = {
    "侦查": "侦察",
    "图书馆": "图书馆使用",
    "计算机": "计算机使用 Ω",
    "驾驶": "汽车驾驶",
    "外语": "语言",
}
ATTR_KEYS = {
    "力量": "str_score", "体质": "con_score", "体型": "siz_score", "敏捷": "dex_score",
    "外貌": "app_score", "智力": "int_score", "意志": "pow_score", "教育": "edu_score",
    "STR": "str_score", "CON": "con_score", "SIZ": "siz_score", "DEX": "dex_score",
    "APP": "app_score", "INT": "int_score", "POW": "pow_score", "EDU": "edu_score",
}

# STR+SIZ → (伤害加值, 体格)
DB_TABLE = ((2, -2, -2), (65, -1, -1), (85, 0, 0), (125, "+1D4", 1), (165, "+1D6", 2))

# 年龄调整表（守密人核心规则书 创建调查员流程）。phy 为体能项，phy_quota 为合计扣减额度，
# 扣在哪几项由玩家分配；edu_checks 为 EDU 成长检定次数，edu_fixed 为固定增减。
AGE_BANDS = (
    {"band": "15-19", "min": 15, "max": 19, "phy": ("str", "siz"), "phy_quota": 5,
     "app": 0, "edu_checks": 0, "edu_fixed": -5, "luck_best": True},
    {"band": "20-39", "min": 20, "max": 39, "phy": (), "phy_quota": 0,
     "app": 0, "edu_checks": 1, "edu_fixed": 0, "luck_best": False},
    {"band": "40-49", "min": 40, "max": 49, "phy": ("str", "con", "dex"), "phy_quota": 5,
     "app": 5, "edu_checks": 2, "edu_fixed": 0, "luck_best": False},
    {"band": "50-59", "min": 50, "max": 59, "phy": ("str", "con", "dex"), "phy_quota": 10,
     "app": 10, "edu_checks": 3, "edu_fixed": 0, "luck_best": False},
    {"band": "60-69", "min": 60, "max": 69, "phy": ("str", "con", "dex"), "phy_quota": 20,
     "app": 15, "edu_checks": 4, "edu_fixed": 0, "luck_best": False},
    {"band": "70-79", "min": 70, "max": 79, "phy": ("str", "con", "dex"), "phy_quota": 40,
     "app": 20, "edu_checks": 4, "edu_fixed": 0, "luck_best": False},
    {"band": "80-89", "min": 80, "max": 89, "phy": ("str", "con", "dex"), "phy_quota": 80,
     "app": 25, "edu_checks": 4, "edu_fixed": 0, "luck_best": False},
    {"band": "90+", "min": 90, "max": 999, "phy": ("str", "con", "dex"), "phy_quota": 80,
     "app": 25, "edu_checks": 4, "edu_fixed": 0, "luck_best": False},
)
AGE_MIN, AGE_MAX = 15, 99
AGE_ATTR_FIELDS = {"str": "str_score", "con": "con_score", "siz": "siz_score",
                   "dex": "dex_score", "app": "app_score", "edu": "edu_score"}
AGE_ATTR_LABELS = {"str": "力量", "con": "体质", "siz": "体型", "dex": "敏捷",
                   "app": "外貌", "edu": "教育"}


def _clamp_or(value, default: int, upper: int | None = None) -> int:
    """当前值缺省取 default；有值时截断到 0..upper（缺省 upper=default）。"""
    cap = default if upper is None else upper
    try:
        number = int(value)
    except (TypeError, ValueError):
        return min(default, cap)
    return max(0, min(number, cap))


def _score(data: dict, key: str) -> int:
    try:
        return int(data.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def scores(data: dict) -> dict:
    return {attr: _score(data, key) for attr, key in ATTR_KEYS.items() if len(attr) > 1}


def db_build(total: int):
    """STR+SIZ → (伤害加值, 体格)。"""
    if total <= 64:
        return -2, -2
    if total <= 84:
        return -1, -1
    if total <= 124:
        return 0, 0
    if total <= 164:
        return "+1D4", 1
    if total <= 204:
        return "+1D6", 2
    steps = (total - 205) // 80
    return f"+{steps + 2}D6", steps + 3


def age_band(age):
    """返回年龄对应的调整表条目；未填（0/空）或超出 15-99 时返回 None。"""
    try:
        years = int(age or 0)
    except (TypeError, ValueError):
        return None
    if not (AGE_MIN <= years <= AGE_MAX):
        return None
    for band in AGE_BANDS:
        if band["min"] <= years <= band["max"]:
            return band
    return None


def age_adjustment(age):
    """给页面/接口用的年龄调整说明；未填或超出范围返回 None。"""
    band = age_band(age)
    if band is None:
        return None
    return {
        "band": band["band"],
        "phy": list(band["phy"]),
        "phy_labels": [AGE_ATTR_LABELS[key] for key in band["phy"]],
        "phy_quota": band["phy_quota"],
        "app": band["app"],
        "edu_checks": band["edu_checks"],
        "edu_fixed": band["edu_fixed"],
        "luck_best": band["luck_best"],
        "mov": age_mov_penalty(age),
    }


def age_bands_payload() -> list:
    """整张年龄表（前端按年龄选段，避免再复制一份）。"""
    return [dict(band, phy=list(band["phy"]),
                 phy_labels=[AGE_ATTR_LABELS[key] for key in band["phy"]])
            for band in AGE_BANDS]


def age_mov_penalty(age) -> int:
    """40 岁起每十年 MOV -1，与人物卡公式 INT(年龄/10)-3 一致（90 岁以上仍继续递减）。"""
    try:
        years = int(age or 0)
    except (TypeError, ValueError):
        years = 0
    return max(0, years // 10 - 3)


def apply_age_adjust(data: dict, phy: dict | None = None, roll=None) -> dict:
    """按年龄调整属性，返回需要合并进卡片的字段（含 age_adjust）。

    体能合计扣减由玩家分配（phy 传负数），EDU 成长检定在服务端掷（刷新页面不能重掷）。
    """
    roll = roll or random.randint
    band = age_band(data.get("age"))
    if band is None:
        raise ValueError(f"请先填写 {AGE_MIN}-{AGE_MAX} 之间的年龄")
    phy = phy or {}
    unknown = set(phy) - set(band["phy"])
    if unknown:
        raise ValueError(
            f"{band['band']} 岁的体能调整只能填："
            + "、".join(AGE_ATTR_LABELS[key] for key in band["phy"]))
    deltas = {}
    for key in band["phy"]:
        try:
            value = int(phy.get(key, 0))
        except (TypeError, ValueError):
            raise ValueError(f"{AGE_ATTR_LABELS[key]}的调整值必须是整数") from None
        if value > 0:
            raise ValueError(f"{AGE_ATTR_LABELS[key]}的调整值必须是 0 或负数")
        deltas[key] = value
    spent = -sum(deltas.values())
    if spent != band["phy_quota"]:
        raise ValueError(f"体能合计应扣 {band['phy_quota']} 点，当前为 {spent} 点")

    changes, before = {}, {}
    for key, delta in deltas.items():
        field = AGE_ATTR_FIELDS[key]
        current = _score(data, field)
        after = current + delta
        if after < 1:
            raise ValueError(f"{AGE_ATTR_LABELS[key]}扣减后为 {after}，属性不能低于 1")
        before[key] = current
        changes[field] = after
    app_before = _score(data, "app_score")
    app_after = app_before - band["app"]
    if app_after < 1:
        raise ValueError(f"外貌扣减后为 {app_after}，属性不能低于 1")
    before["app"] = app_before
    changes["app_score"] = app_after

    edu_before = _score(data, "edu_score")
    edu = edu_before + band["edu_fixed"]
    if edu < 1:
        raise ValueError(f"教育扣减后为 {edu}，属性不能低于 1")
    rolls = []
    for _ in range(band["edu_checks"]):
        dice = roll(1, 100)
        gain = 0
        if dice > edu:
            gain = roll(1, 10)
            edu = min(SKILL_MAX, edu + gain)
        rolls.append({"roll": dice, "gain": gain})
    changes["edu_score"] = edu

    changes["age_adjust"] = {
        "kind": "applied",
        "age": int(data["age"]),
        "band": band["band"],
        "phy": deltas,
        "app": -band["app"],
        "edu": {"before": edu_before, "after": edu, "checks": band["edu_checks"], "rolls": rolls},
        "before": before,
        "applied_at": int(time.time()),
    }
    return changes


def undo_age_adjust(data: dict) -> dict:
    """按 age_adjust.before 还原属性；返回需要合并进卡片的字段。"""
    record = data.get("age_adjust")
    if not isinstance(record, dict) or record.get("kind") != "applied":
        raise ValueError("这张卡没有可撤销的年龄调整")
    before = record.get("before") or {}
    restored = {}
    for key, value in before.items():
        field = AGE_ATTR_FIELDS.get(key)
        if field:
            restored[field] = int(value)
    edu = record.get("edu") or {}
    if edu.get("before") is not None:
        restored["edu_score"] = int(edu["before"])
    return restored


def base_mov(str_score: int, dex_score: int, siz_score: int) -> int:
    if str_score > siz_score and dex_score > siz_score:
        return 9
    if str_score < siz_score and dex_score < siz_score:
        return 7
    return 8


def occupation_by_name(name: str):
    from .occupation_details import OCCUPATION_DETAILS

    for seq, job, low, high, formula, own in OCCUPATIONS:
        if job == name:
            extra = OCCUPATION_DETAILS.get(seq) or {}
            return {"seq": seq, "name": job, "credit_min": low, "credit_max": high,
                    "formula": formula, "own_skills": own,
                    "contacts": extra.get("contacts", ""),
                    "description": extra.get("description", "")}
    return None


def occupation_slots(seq) -> dict | None:
    """结构化本职技能定义：{required: [...], choices: [{count, from}]}。"""
    return OCCUPATION_SKILLS.get(str(seq))


def _parsed_pools(struct: dict) -> list[dict]:
    """把职业定义里的可选池展开成可比较结构。"""
    pools = []
    for choice in struct.get("choices") or []:
        source = choice.get("from")
        count = int(choice.get("count") or 0)
        if source == "*":
            pools.append({"count": count, "exact": set(), "wild": [], "star": True})
            continue
        exact, wild = set(), []
        for name in source or []:
            fixed = canonical_skill(name)
            if fixed.endswith(":*"):
                wild.append(fixed[:-1])
            else:
                exact.add(fixed)
        pools.append({"count": count, "exact": exact, "wild": wild, "star": False})
    return pools


def _pool_accepts(pool: dict, name: str) -> bool:
    if pool["star"]:
        return True
    return name in pool["exact"] or any(name.startswith(prefix) for prefix in pool["wild"])


def occupation_structure(data: dict):
    """返回 (职业, 固定项集合, 通配前缀, 池列表)；无职业或无定义时返回 None。"""
    occ = occupation_by_name((data.get("occupation") or "").strip())
    if not occ:
        return None
    struct = occupation_slots(occ["seq"])
    if not struct:
        return None
    required = {canonical_skill(name) for name in struct.get("required") or []}
    wildcards = [name[:-1] for name in required if name.endswith(":*")]
    return occ, required, wildcards, _parsed_pools(struct)


def occupation_choice_problems(data: dict) -> list[str]:
    """可选池的选择本身是否合法：技能存在、落在对应池、不超配额。"""
    info = occupation_structure(data)
    if not info:
        return []
    occ, _, _, pools = info
    choices = data.get("occupation_choices")
    if not isinstance(choices, dict):
        return []
    problems = []
    for index, raw_list in choices.items():
        pool_index = int(index) if str(index).isdigit() else -1
        if not 0 <= pool_index < len(pools):
            problems.append(f"{occ['name']}没有第 {index} 个可选池")
            continue
        pool = pools[pool_index]
        names = [str(n).strip() for n in (raw_list or []) if str(n).strip()]
        if len(names) > pool["count"]:
            problems.append(
                f"{occ['name']}的可选池 #{pool_index + 1} 最多选 {pool['count']} 项（已选 {len(names)}）")
        for name in names:
            fixed = canonical_skill(name)
            if not skill_name_ok(fixed):
                problems.append(f"可选技能「{name}」不在技能表内")
            elif not _pool_accepts(pool, fixed):
                problems.append(f"「{name}」不在{occ['name']}的可选池 #{pool_index + 1} 中")
    return problems


def occupation_choice_warnings(data: dict) -> list[str]:
    """池没选满时给出提示（不阻止保存）。"""
    info = occupation_structure(data)
    if not info:
        return []
    occ, _, _, pools = info
    choices = data.get("occupation_choices") or {}
    warnings = []
    for index, pool in enumerate(pools):
        picked = len([n for n in (choices.get(str(index)) or []) if str(n).strip()])
        if picked < pool["count"]:
            warnings.append(f"{occ['name']}的可选池 #{index + 1} 还差 {pool['count'] - picked} 项")
    return warnings


def occupational_point_problems(data: dict) -> list[str]:
    """职业点只能加在固定项或**已选定**的可选池技能上。"""
    info = occupation_structure(data)
    if not info:
        return []
    occ, required, wildcards, _ = info
    chosen = set()
    for names in (data.get("occupation_choices") or {}).values():
        for name in names or []:
            chosen.add(canonical_skill(str(name)))

    problems = []
    for raw_name, entry in (data.get("skills") or {}).items():
        if not isinstance(entry, dict):
            continue
        try:
            points = int(entry.get("occupation") or 0)
        except (TypeError, ValueError):
            continue
        if points <= 0:
            continue
        name = canonical_skill(raw_name)
        if name == CREDIT_SKILL:
            continue                  # 信用评级对所有职业都算本职技能（补到下限）
        if name in required or any(name.startswith(prefix) for prefix in wildcards):
            continue
        if name in chosen:
            continue
        problems.append(
            f"技能「{raw_name}」不是{occ['name']}的本职技能，不能加职业点"
        )
    return problems


def points_budget(formula: str, data: dict) -> int:
    """解析「教育×4」「教育×2＋敏捷×2」「教育×2＋力量或敏捷×2」这类公式。"""
    total = 0
    for term in (formula or "").replace("＋", "+").split("+"):
        term = term.strip()
        if not term:
            continue
        multiplier = 1
        if "×" in term:
            head, _, tail = term.partition("×")
            term = head.strip()
            try:
                multiplier = int(tail.strip() or 1)
            except ValueError:
                multiplier = 1
        options = [part.strip() for part in term.split("或") if part.strip()]
        values = [_score(data, ATTR_KEYS[opt]) for opt in options if opt in ATTR_KEYS]
        if values:
            total += max(values) * multiplier
    return total


def skill_total(entry: dict) -> int:
    total = 0
    for key in ("base", "growth", "occupation", "interest"):
        try:
            total += int(entry.get(key) or 0)
        except (TypeError, ValueError):
            continue
    return min(total, SKILL_CEILING)


def canonical_skill(name: str) -> str:
    key = (name or "").strip()
    return SKILL_ALIASES.get(key, key)


def skill_name_ok(name: str) -> bool:
    name = canonical_skill(name)
    if not name:
        return False
    if name in SKILL_BASE:
        return True
    # 武器技能（斗殴、手枪、步枪/霰弹枪…）也是合法技能名，只是不在 39 项标准表里
    if name in weapon_skill_base():
        return True
    return any(name.startswith(cat) for cat in SKILL_CATEGORIES)


# 附表里武器技能的写法与规则书/武器库不一致的一处
WEAPON_SKILL_ALIASES = {"弓术": "弓"}


def _percent_value(text) -> int | None:
    matched = re.match(r"^\s*(\d+)", str(text or ""))
    return int(matched.group(1)) if matched else None


def weapon_skill_base() -> dict[str, int]:
    """武器技能的基础成功率（斗殴 25、手枪 20、步枪/霰弹枪 25…），取自武器库与附表。"""
    from .skill_notes import SKILL_NOTES
    from .weapon_data import WEAPONS

    table = {}
    for skill in {w["skill"] for w in WEAPONS}:
        canon = canonical_skill(skill)
        note = SKILL_NOTES.get(canon) or SKILL_NOTES.get(
            next((alias for alias, fixed in WEAPON_SKILL_ALIASES.items() if fixed == canon), ""), None)
        base = _percent_value((note or {}).get("base"))
        if base is not None:
            table[canon] = base
    return table


# 附表里的技能名与角色卡上的规范名不一致的几处
NOTE_ALIASES = {
    "取悦": "魅惑",
    "侦查": "侦察",
    "导航": "领航",
    "计算机使用": "计算机使用 Ω",
    "艺术与手艺": "技艺",
}


def skill_note_index() -> dict[str, dict]:
    """技能说明索引：以角色卡上的规范名建键，别名与原表名都能查到。"""
    from .skill_notes import SKILL_NOTES

    index = dict(SKILL_NOTES)
    for raw, canon in NOTE_ALIASES.items():
        note = SKILL_NOTES.get(raw)
        if note and canon not in index:
            index[canon] = note
    return index


# 由属性派生的基础值（不写死数字，随属性变化）
DYNAMIC_BASES = {
    "闪避": {"attr": "dex_score", "divisor": 2, "label": "敏捷÷2"},
    "母语": {"attr": "edu_score", "divisor": 1, "label": "教育"},
}


def dynamic_skill_base(name: str, data: dict) -> int | None:
    """闪避 = DEX/2、母语 = EDU；不是动态技能返回 None。"""
    rule = DYNAMIC_BASES.get(canonical_skill(name))
    if not rule:
        return None
    try:
        value = int(data.get(rule["attr"]) or 0)
    except (TypeError, ValueError):
        return 0
    return max(value // rule["divisor"], 0)


def skill_base_for(name: str, data: dict | None = None) -> int:
    """任意技能的基础值：先看动态规则，再查静态表。"""
    canon = canonical_skill(name)
    if data is not None:
        dynamic = dynamic_skill_base(canon, data)
        if dynamic is not None:
            return dynamic
    return skill_base_map().get(canon, 0)


def skill_base_map() -> dict[str, int]:
    """所有已知技能的基础值：标准 39 项 + 附表专攻（技艺:表演…）+ 武器技能（斗殴…）。

    这是「某技能基础成功率是多少」的唯一来源——finalize 的兜底、成长补行、
    网页播种与武器成功率都用它，避免同一技能在不同路径算出不同数字。
    """
    table = {canonical_skill(name): int(base or 0) for name, base in SKILL_BASE.items()}
    from .skill_notes import SKILL_NOTES

    for name, note in SKILL_NOTES.items():
        base = _percent_value(note.get("base"))
        key = canonical_skill(NOTE_ALIASES.get(name, name)).rstrip("：:")
        if base is not None and key not in table:
            table[key] = base
    for name, base in weapon_skill_base().items():
        table.setdefault(name, base)
    return table


def default_skill_names() -> list[str]:
    """建卡时铺进技能表的标准技能（专攻与武器技能不铺，避免每张卡多出几十行）。"""
    return [canonical_skill(name) for name in SKILL_BASE]


def skill_defaults(dex_score: int, edu_score: int = 0) -> dict[str, int]:
    """标准技能的默认基础值；闪避按 DEX/2、母语按 EDU 派生。"""
    table = skill_base_map()
    defaults = {name: table.get(name, 0) for name in default_skill_names()}
    defaults["闪避"] = max(int(dex_score or 0) // 2, 0)
    defaults["母语"] = max(int(edu_score or 0), 0)
    return defaults


def finalize(data: dict) -> dict:
    """按 COC 7th 口径算派生值；返回可直接给网页/机器人用的大字典。"""
    out = dict(data)
    str_score = _score(data, "str_score")
    con_score = _score(data, "con_score")
    siz_score = _score(data, "siz_score")
    dex_score = _score(data, "dex_score")
    app_score = _score(data, "app_score")
    int_score = _score(data, "int_score")
    pow_score = _score(data, "pow_score")
    edu_score = _score(data, "edu_score")

    db, build = db_build(str_score + siz_score)
    occupation = occupation_by_name((data.get("occupation") or "").strip())
    skills = {}
    for raw_name, entry in (data.get("skills") or {}).items():
        name = canonical_skill(raw_name)
        if not isinstance(entry, dict) or not skill_name_ok(name):
            continue
        base = entry.get("base")
        dynamic = dynamic_skill_base(name, data)
        if dynamic is not None:
            # 闪避/母语的基础值由属性决定，卡上存的值不作为口径
            base = dynamic
        elif base is None:
            base = skill_base_map().get(name, 0)
        merged = {
            "base": int(base or 0),
            "growth": int(entry.get("growth") or 0),
            "occupation": int(entry.get("occupation") or 0),
            "interest": int(entry.get("interest") or 0),
        }
        merged["total"] = skill_total(merged)
        skills[raw_name] = merged

    # 规则默认值：卡上没有写过的标准技能，按技能表补出基础成功率
    stored = {canonical_skill(name) for name in skills}
    for name, base in skill_defaults(dex_score, edu_score).items():
        if name in stored:
            continue
        entry = {"base": base, "growth": 0, "occupation": 0, "interest": 0}
        entry["total"] = skill_total(entry)
        skills[name] = entry

    # 信用评级：职业点补到下限，之后可用兴趣点；基础值与成长不参与
    credit_row = credit_entry(data) or {}
    credit_points = {
        "base": 0,
        "growth": 0,
        "occupation": int(credit_row.get("occupation") or 0),
        "interest": int(credit_row.get("interest") or 0),
    }
    credit_points["total"] = min(credit_points["occupation"] + credit_points["interest"], 99)
    skills[CREDIT_SKILL] = credit_points

    occupation_spent = sum(entry["occupation"] for entry in skills.values())
    interest_spent = sum(entry["interest"] for entry in skills.values())

    max_san = max(99 - int(data.get("cthulhu_mythos") or 0), 0)
    derived_hp = max((con_score + siz_score) // 10, 0)
    derived_mp = max(pow_score // 5, 0)
    current_hp = _clamp_or(data.get("current_hp"), derived_hp)
    current_mp = _clamp_or(data.get("current_mp"), derived_mp)
    current_san = _clamp_or(data.get("current_san"), max(pow_score, 0), max_san)

    out.update({
        "rules": "coc7th",
        "scores": {
            "力量": str_score, "体质": con_score, "体型": siz_score, "敏捷": dex_score,
            "外貌": app_score, "智力": int_score, "意志": pow_score, "教育": edu_score,
        },
        "hp": derived_hp,
        "mp": derived_mp,
        "san": max(pow_score, 0),
        "max_san": max_san,
        "current_hp": current_hp,
        "current_mp": current_mp,
        "current_san": current_san,
        "mov": max(base_mov(str_score, dex_score, siz_score) - age_mov_penalty(data.get("age")), 0),
        "db": str(db),
        "build": build,
        "dodge": dex_score // 2,
        "credit_rating": credit_value(data),
        "skills": skills,
        "occupation_info": occupation,
        "occupation_budget": points_budget(occupation["formula"], data) if occupation else 0,
        "occupation_spent": occupation_spent,
        "interest_budget": int_score * 2,
        "interest_spent": interest_spent,
    })
    return out


# 伤害列里的非骰修饰：DB 变体、状态效果、规则关键词（连同前面的 + / - 一起去掉）
DAMAGE_MODIFIER_RE = re.compile(r"[+-]?\s*(半DB|DB|燃烧|眩晕|出血|中毒|伤害等级|即死|特殊)")


def _damage_segment_ok(segment: str) -> bool:
    seg = DAMAGE_MODIFIER_RE.sub("", segment.strip()).strip()
    if not seg or seg in DASHES:
        return True
    parts = [part.strip() for part in re.split(r"[+-]", seg)]
    if not parts or any(not part for part in parts):
        return False
    for part in parts:
        if part.isdigit() and 0 <= int(part) <= 999:
            continue
        matched = DICE_TERM_RE.match(part)
        if not matched:
            return False
        count = int(matched.group(1) or 1)
        sides = int(matched.group(2))
        if not 1 <= count <= 20 or not 2 <= sides <= 1000:
            return False
    return True


def weapon_skill_ok(name: str) -> bool:
    """武器使用技能：技能表里的名字、类别专攻写法，或武器库里出现的武器技能。"""
    from .weapon_data import WEAPONS

    fixed = canonical_skill(str(name or "").strip())
    if fixed in SKILL_BASE:
        return True
    if fixed in {w["skill"] for w in WEAPONS}:
        return True
    for category in set(SKILL_CATEGORIES):
        if fixed.startswith(category):
            rest = fixed[len(category):].lstrip(":")
            return bool(rest) and skill_name_ok(f"{category}:{rest}")
    return False


def level_for_credit(credit) -> str:
    """信用评级 → 生活水平档位（0 / 1-9 / 10-49 / 50-89 / 90-98 / 99）。"""
    from .asset_data import LEVELS

    try:
        value = int(credit)
    except (TypeError, ValueError):
        return ""
    for level in LEVELS:
        if level["min"] <= value <= level["max"]:
            return level["name"]
    return ""


def _asset_value(formula, credit: int):
    mode, value = formula
    if mode == "x":
        return int(round(credit * value))
    if mode == "flat":
        return value
    return value  # text：原样给前端展示


def asset_reference(currency: str, credit, level: str = "") -> dict | None:
    """按币种 + 信用评级（或指定档位）查现金 / 其他资产 / 消费水平参考值。"""
    from .asset_data import CURRENCIES

    table = next((c for c in CURRENCIES if c["code"] == currency), None)
    if table is None:
        return None
    try:
        score = int(credit)
    except (TypeError, ValueError):
        score = 0
    name = level if level in table["rows"] else level_for_credit(score)
    row = table["rows"].get(name)
    if row is None:
        return None
    return {
        "level": name,
        "cash": _asset_value(row["cash"], score),
        "other": _asset_value(row["other"], score),
        "spending": _asset_value(row["spending"], score),
    }


def damage_with_db(damage: str, db: str) -> str:
    """伤害列展示：原文 + 当前伤害加值标注，如「1D6+DB（当前 DB=1D4）」。"""
    text = str(damage or "").strip()
    if not text or "DB" not in text:
        return text
    return f"{text}（当前 DB={db or 0}）"


def damage_ok(text) -> bool:
    """伤害列允许：数字、NdM、多项相加、+DB / +半DB、斜杠分隔的多档伤害（霰弹）与状态修饰。"""
    raw = str(text or "").strip().replace("＋", "+").replace("－", "-").replace("：", ":")
    if raw in DASHES:
        return True
    # 霰弹枪一类按距离分档：2D6/1D6/1D3；「4D10/5码」这类爆破半径后缀先摘掉
    raw = re.sub(r"/\s*\d+\s*码$", "", raw)
    segments = raw.split("/")
    return all(_damage_segment_ok(seg) for seg in segments)


ASSET_NUMBER_MAX = 10 ** 15

INVENTORY_STATUSES = ("装备", "携带", "背包")
INVENTORY_ROWS_MAX = 40
INVENTORY_SLOT_MAX = 20


def inventory_problems(items) -> list[str]:
    """随身物品：状态三态、名称必填不重名、背包格 0-20。"""
    if items in (None, ""):
        return []
    if not isinstance(items, list):
        return ["随身物品格式错误"]
    problems = []
    if len(items) > INVENTORY_ROWS_MAX:
        problems.append(f"随身物品最多 {INVENTORY_ROWS_MAX} 行（当前 {len(items)}）")
    seen = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            problems.append(f"物品 #{index} 格式错误")
            continue
        name = str(item.get("name") or "").strip()
        label = f"物品「{name}」" if name else f"物品 #{index}"
        if not name:
            problems.append(f"物品 #{index} 缺少名称")
        else:
            if len(name) > 30:
                problems.append(f"{label}名称过长（上限 30 字）")
            if name.casefold() in seen:
                problems.append(f"{label}重复添加")
            seen.add(name.casefold())
        status = str(item.get("status") or "").strip()
        if status and status not in INVENTORY_STATUSES:
            problems.append(f"{label}的状态「{status}」不在 {'/'.join(INVENTORY_STATUSES)} 之内")
        slots = item.get("slots")
        if slots not in (None, ""):
            try:
                value = int(slots)
            except (TypeError, ValueError):
                problems.append(f"{label}的背包格必须是整数")
            else:
                if not 0 <= value <= INVENTORY_SLOT_MAX:
                    problems.append(f"{label}的背包格应在 0-{INVENTORY_SLOT_MAX}（当前 {value}）")
    return problems


def inventory_summary(data: dict) -> tuple[list[dict], int]:
    """随身物品按状态分组后的条目与总格数。"""
    items = [i for i in (data.get("inventory") or []) if isinstance(i, dict) and str(i.get("name") or "").strip()]
    slots = 0
    for item in items:
        try:
            slots += int(item.get("slots") or 0)
        except (TypeError, ValueError):
            continue
    return items, slots


def asset_problems(assets) -> list[str]:
    """资产栏校验：币种与生活水平必须是表里的值，其他资产表必须是非负数字。"""
    from .asset_data import ASSET_ITEM_FIELDS, CURRENCIES, LEVELS

    if assets in (None, ""):
        return []
    if not isinstance(assets, dict):
        return ["资产栏格式错误"]
    problems = []
    codes = {c["code"] for c in CURRENCIES}
    currency = str(assets.get("currency") or "").strip()
    if currency and currency not in codes:
        problems.append(f"未知币种「{currency}」（可用：{'、'.join(sorted(codes))}）")
    levels = {level["name"] for level in LEVELS}
    level = str(assets.get("living_standard") or "").strip()
    if level and level not in levels:
        problems.append(f"生活水平「{level}」不在 6 档之内（{'、'.join(l['name'] for l in LEVELS)}）")
    for key, label in ASSET_ITEM_FIELDS:
        raw = assets.get(key)
        if raw in (None, ""):
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            problems.append(f"其他资产「{label}」必须是整数")
            continue
        if not 0 <= value <= ASSET_NUMBER_MAX:
            problems.append(f"其他资产「{label}」应在 0-{ASSET_NUMBER_MAX} 之间")
    return problems


def weapon_problems(weapons) -> list[str]:
    problems = []
    if not isinstance(weapons, list):
        return ["武器表格式错误"]
    if len(weapons) > WEAPON_ROWS_MAX:
        problems.append(f"武器最多 {WEAPON_ROWS_MAX} 行（当前 {len(weapons)}）")
    seen = set()
    for index, weapon in enumerate(weapons, start=1):
        if not isinstance(weapon, dict):
            problems.append(f"武器 #{index} 格式错误")
            continue
        name = str(weapon.get("name") or "").strip()
        label = f"武器「{name}」" if name else f"武器 #{index}"
        if not name:
            problems.append(f"武器 #{index} 缺少名称")
        else:
            if len(name) > WEAPON_NAME_MAX:
                problems.append(f"{label}名称过长（上限 {WEAPON_NAME_MAX} 字）")
            if name.casefold() in seen:
                problems.append(f"{label}重复添加")
            seen.add(name.casefold())
        success = weapon.get("success")
        if success not in (None, ""):
            try:
                value = int(success)
            except (TypeError, ValueError):
                problems.append(f"{label}的成功率必须是数字")
            else:
                if not 0 <= value <= 99:
                    problems.append(f"{label}的成功率应在 0-99（当前 {value}）")
        skill = str(weapon.get("skill") or "").strip()
        if not skill:
            problems.append(f"{label}缺少使用技能（例：斗殴、手枪、射击:步枪）")
        elif not weapon_skill_ok(skill):
            problems.append(
                f"{label}的使用技能「{skill}」不在技能表里（可用：斗殴、手枪、步枪/霰弹枪、弓、投掷…）")
        if not damage_ok(weapon.get("damage")):
            problems.append(f"{label}的伤害「{weapon.get('damage')}」不是合法写法（例：1D8、1D3+DB、1D10+1D4）")
        malfunction = str(weapon.get("malfunction") or "").strip()
        if malfunction not in DASHES:
            try:
                value = int(malfunction)
            except (TypeError, ValueError):
                problems.append(f"{label}的故障值必须是数字（0-100）")
            else:
                if not 0 <= value <= 100:
                    problems.append(f"{label}的故障值应在 0-100（当前 {value}）")
        attacks = str(weapon.get("attacks") or "").strip()
        if attacks not in DASHES and attacks not in ATTACKS_TEXT_OK and not ATTACKS_RE.match(attacks):
            problems.append(f"{label}的次数应写成 1 或 1(3)（当前「{attacks}」）")
        for field, limit in WEAPON_TEXT_MAX.items():
            value = str(weapon.get(field) or "").strip()
            if len(value) > limit:
                problems.append(f"{label}的{WEAPON_FIELD_LABEL[field]}过长（上限 {limit} 字）")
    return problems


def age_adjust_problems(data: dict) -> list[str]:
    """年龄与年龄调整记录的一致性校验；未处理（无 age_adjust）的卡不参与。"""
    problems = []
    raw_age = data.get("age")
    try:
        years = int(raw_age or 0)
    except (TypeError, ValueError):
        return ["年龄必须是整数"]
    if years and not (AGE_MIN <= years <= AGE_MAX):
        return [f"年龄应在 {AGE_MIN}-{AGE_MAX} 之间"]
    record = data.get("age_adjust")
    if not record:
        return problems
    if not isinstance(record, dict) or record.get("kind") not in ("applied", "skipped"):
        return ["年龄调整记录格式不正确"]
    if record.get("kind") == "skipped":
        return problems
    band = age_band(years)
    if band is None:
        return problems
    if int(record.get("age") or 0) != years:
        return [f"年龄已从 {record.get('age')} 改为 {years}，请重新应用或撤销年龄调整"]
    if record.get("band") != band["band"]:
        return ["年龄调整记录与年龄段不符，请撤销后重新应用"]

    phy = record.get("phy") or {}
    if set(phy) != set(band["phy"]):
        return ["年龄调整记录与年龄段不符，请撤销后重新应用"]
    try:
        deltas = {key: int(value) for key, value in phy.items()}
    except (TypeError, ValueError):
        return ["年龄调整记录格式不正确"]
    if any(value > 0 for value in deltas.values()):
        return ["年龄调整记录格式不正确"]
    spent = -sum(deltas.values())
    if spent != band["phy_quota"]:
        return [f"体能合计应扣 {band['phy_quota']} 点，当前为 {spent} 点"]

    before = record.get("before") or {}
    for key, delta in deltas.items():
        field = AGE_ATTR_FIELDS[key]
        expected = int(before.get(key) or 0) + delta
        if _score(data, field) != expected:
            return [f"年龄调整后请勿手工修改{AGE_ATTR_LABELS[key]}，如需修改请先撤销年龄调整"]
    app_expected = int(before.get("app") or 0) - band["app"]
    if _score(data, "app_score") != app_expected:
        return ["年龄调整后请勿手工修改外貌，如需修改请先撤销年龄调整"]
    edu_record = record.get("edu") or {}
    edu_after = int(edu_record.get("after") or 0)
    if _score(data, "edu_score") != edu_after:
        return ["年龄调整后请勿手工修改教育，如需修改请先撤销年龄调整"]
    return problems


def validate(data: dict) -> list[str]:
    """建卡约束：属性范围、技能点不超预算、信用评级在职业区间内。"""
    normalize_credit_rating(data)
    problems = []
    fin = finalize(data)
    for attr, value in fin["scores"].items():
        if value and not (1 <= value <= 99):
            problems.append(f"{attr}应在 1-99 之间")
    if fin["occupation_info"] is None:
        # 未选职业允许存在：此时没有职业点预算，职业点必须为 0
        if fin["occupation_spent"] > 0:
            problems.append("未选择职业时不能分配职业点")
    else:
        if fin["occupation_spent"] > fin["occupation_budget"]:
            problems.append(
                f"职业点超出预算（{fin['occupation_spent']}/{fin['occupation_budget']}）")
        problems.extend(credit_problems(data))
    if fin["interest_spent"] > fin["interest_budget"]:
        problems.append(f"兴趣点超出预算（{fin['interest_spent']}/{fin['interest_budget']}）")
    for name, entry in fin["skills"].items():
        if entry["total"] < 0 or entry["total"] > SKILL_CEILING:
            problems.append(f"技能「{name}」成功率应在 0-{SKILL_CEILING} 之间")
    problems.extend(occupation_choice_problems(data))
    problems.extend(occupational_point_problems(data))
    problems.extend(weapon_problems(data.get("weapons") or []))
    problems.extend(asset_problems(data.get("assets")))
    problems.extend(inventory_problems(data.get("inventory")))
    problems.extend(age_adjust_problems(data))
    return problems


CREDIT_SKILL = "信用评级"


def credit_entry(data: dict) -> dict | None:
    """卡上的信用评级技能行（只读查找）。"""
    skills = data.get("skills")
    if not isinstance(skills, dict):
        return None
    for name, entry in skills.items():
        if canonical_skill(name) == CREDIT_SKILL and isinstance(entry, dict):
            return entry
    return None


def credit_value(data: dict) -> int:
    """信用评级 = 技能行里的职业点 + 兴趣点（基础值恒为 0），钳在 0-99。"""
    entry = credit_entry(data) or {}
    try:
        total = int(entry.get("occupation") or 0) + int(entry.get("interest") or 0)
    except (TypeError, ValueError):
        total = 0
    return max(0, min(total, 99))


def normalize_credit_rating(data: dict) -> bool:
    """信用评级由技能行决定：先迁走资产区的历史值，再把 credit_rating 同步成技能合计。

    迁移规则：技能行合计为 0 而资产区有值时，下限以内算职业点、其余记兴趣点
    （没有职业时全部记兴趣点）。资产参考表与生活水平仍读 `credit_rating`，
    因此这里每次保存都把它写成技能的合计值。
    """
    skills = data.get("skills")
    if not isinstance(skills, dict):
        skills = data["skills"] = {}
    key = next((name for name in skills if canonical_skill(name) == CREDIT_SKILL), CREDIT_SKILL)
    row = skills.get(key)
    if not isinstance(row, dict):
        row = {}
        skills[key] = row

    changed = False
    if row.get("base"):
        row["base"] = 0            # 信用评级没有基础成功率
        changed = True
    if row.get("growth"):
        # 规则禁止给它打成长标记；历史数据里的成长并入职业点，不丢点数
        row["occupation"] = int(row.get("occupation") or 0) + int(row["growth"] or 0)
        row["growth"] = 0
        changed = True

    try:
        spent = int(row.get("occupation") or 0) + int(row.get("interest") or 0)
    except (TypeError, ValueError):
        spent = 0
    if spent == 0:
        try:
            legacy = int(data.get("credit_rating") or 0)
        except (TypeError, ValueError):
            legacy = 0
        if legacy > 0:
            info = occupation_by_name((data.get("occupation") or "").strip())
            occupation_part = min(legacy, info["credit_min"]) if info else 0
            row["occupation"] = occupation_part
            row["interest"] = max(legacy - occupation_part, 0)
            changed = True

    total = credit_value(data)
    if data.get("credit_rating") != total:
        data["credit_rating"] = total
        changed = True
    return changed


def credit_problems(data: dict) -> list[str]:
    """信用评级校验：落在职业区间内；未到下限时只能用职业点加点。"""
    info = occupation_by_name((data.get("occupation") or "").strip())
    if not info:
        return []
    entry = credit_entry(data) or {}
    try:
        occupation_points = int(entry.get("occupation") or 0)
        interest_points = int(entry.get("interest") or 0)
    except (TypeError, ValueError):
        occupation_points = interest_points = 0
    total = occupation_points + interest_points
    low, high = info["credit_min"], info["credit_max"]
    if not (low <= total <= high):
        return [f"信用评级应在 {low}-{high} 之间（当前 {total}）"]
    if interest_points > 0 and occupation_points < low:
        return [f"信用评级未到职业下限 {low} 时只能用职业点加点"
                f"（现在职业点 {occupation_points}、兴趣点 {interest_points}）"]
    return []


def skill_value(data: dict, name: str) -> int | None:
    """取某个技能的最终成功率（先精确匹配，再按类别前缀匹配）。供骰子 `.ra 技能` 使用。"""
    fin = finalize(data)
    key = canonical_skill(name)
    if not key:
        return None
    if key in fin["skills"]:
        return fin["skills"][key]["total"]
    canon = canonical_skill(key)
    for skill, entry in fin["skills"].items():
        if canonical_skill(skill) == canon or skill.startswith(key):
            return entry["total"]
    # 武器技能（斗殴/手枪/射击:步枪…）不在 39 项标准技能里，按规则书基础值兜底
    base = weapon_skill_base().get(WEAPON_SKILL_ALIASES.get(canon, canon))
    if base is not None:
        return base
    return None


# 属性检定用的名字表：中文全称、英文缩写（大小写不敏感）与常用别名
ATTRIBUTE_ALIASES = {
    "力量": "str_score", "STR": "str_score",
    "体质": "con_score", "CON": "con_score",
    "体型": "siz_score", "SIZ": "siz_score",
    "敏捷": "dex_score", "DEX": "dex_score",
    "外貌": "app_score", "APP": "app_score",
    "智力": "int_score", "INT": "int_score",
    "意志": "pow_score", "POW": "pow_score",
    "教育": "edu_score", "EDU": "edu_score",
    "幸运": "luck", "LUCK": "luck",
    "信用评级": "credit_rating", "信用": "credit_rating",
}
ATTRIBUTE_LABELS = {
    "str_score": "力量", "con_score": "体质", "siz_score": "体型", "dex_score": "敏捷",
    "app_score": "外貌", "int_score": "智力", "pow_score": "意志", "edu_score": "教育",
    "luck": "幸运", "credit_rating": "信用评级",
}


def attribute_value(data: dict, name: str):
    """属性名 → (显示名, 数值)；不是属性时返回 None。供骰子 `.ra 力量` 使用。"""
    key = ATTRIBUTE_ALIASES.get((name or "").strip().upper())         or ATTRIBUTE_ALIASES.get((name or "").strip())
    if not key:
        return None
    if key in ("luck", "credit_rating"):
        value = int(data.get(key) or 0)
    else:
        value = _score(data, key)
    return ATTRIBUTE_LABELS[key], value


def format_sheet(data: dict) -> str:
    """机器人 `/跑团 角色 查看` 的精简文本：属性 + 派生 + 非基础技能 + 背景摘要。"""
    fin = finalize(data)
    sc = fin["scores"]
    lines = [
        f"【{fin.get('char_name') or '无名调查员'}】{fin.get('occupation') or '无职业'}"
        f"  {fin.get('age') or '?'}岁 {fin.get('sex') or ''}".rstrip(),
        f"力量{sc['力量']} 体质{sc['体质']} 体型{sc['体型']} 敏捷{sc['敏捷']}",
        f"外貌{sc['外貌']} 智力{sc['智力']} 意志{sc['意志']} 教育{sc['教育']}",
        f"HP {fin['hp']}  MP {fin['mp']}  SAN {fin.get('san')}  幸运 {fin.get('luck') or 0}",
        f"MOV {fin['mov']}  伤害加值 {fin['db']}  体格 {fin['build']}  闪避 {fin['dodge']}",
    ]
    notable = [
        (name, entry) for name, entry in fin["skills"].items()
        if entry["total"] > SKILL_BASE.get(canonical_skill(name), 0)
    ]
    if notable:
        notable.sort(key=lambda item: item[1]["total"], reverse=True)
        lines.append("技能：" + "、".join(f"{name} {entry['total']}%" for name, entry in notable[:12]))
    weapons = data.get("weapons") or []
    if isinstance(weapons, list) and weapons:
        lines.append("武器：")
        for weapon in weapons[:6]:
            if not isinstance(weapon, dict):
                continue
            name = str(weapon.get("name") or "").strip()
            if not name:
                continue
            parts = [f"  {name}"]
            skill = str(weapon.get("skill") or "").strip()
            if skill:
                parts.append(f"{skill}")
            damage = damage_with_db(weapon.get("damage"), fin["db"])
            if damage:
                parts.append(damage)
            if str(weapon.get("range") or "").strip():
                parts.append(f"射程 {weapon['range']}")
            lines.append("｜".join(parts))
    items, slots = inventory_summary(data)
    if items:
        names = []
        for item in items[:6]:
            status = str(item.get("status") or "").strip()
            name = str(item.get("name") or "").strip()
            names.append(f"{name}（{status}）" if status else name)
        tail = f"… 共 {len(items)} 件 · {slots} 格" if len(items) > 6 else f"共 {len(items)} 件 · {slots} 格"
        lines.append("装备：" + "、".join(names) + f"\n       {tail}")
    assets = data.get("assets") or {}
    if isinstance(assets, dict) and any(str(assets.get(k) or "").strip()
                                        for k in ("cash", "other_assets", "currency", "living_standard")):
        from .asset_data import CURRENCIES

        parts = []
        currency = next((c["label"] for c in CURRENCIES if c["code"] == assets.get("currency")), "")
        if currency:
            parts.append(currency)
        if assets.get("living_standard"):
            parts.append(f"生活水平 {assets['living_standard']}")
        if str(assets.get("cash") or "").strip():
            parts.append(f"现金 {assets['cash']}")
        if str(assets.get("other_assets") or "").strip():
            parts.append(f"其他资产 {assets['other_assets']}")
        if parts:
            lines.append("资产：" + " · ".join(parts))
    background = data.get("background") or {}
    if isinstance(background, dict):
        traits = background.get("traits") or ""
        if traits:
            lines.append(f"特质：{traits}")
    notes = (data.get("notes") or "").strip()
    if notes:
        lines.append(f"备注：{notes[:80]}")
    return "\n".join(lines)
