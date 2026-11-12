"""COC 7th 角色卡：派生值、技能点预算与人物卡文本。

建卡逻辑对齐 docs/COC七版人物卡v1.6.1.xlsx：属性手填/掷骰，年龄只影响 MOV（附表口径），
技能 = 基础值 + 成长 + 职业点 + 兴趣点（上限 99），职业点预算按职业公式、兴趣点 = 智力×2，
信用评级受职业区间约束。伤害加值与体格按 STR+SIZ 查表。
"""

from __future__ import annotations

import re

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

# 年龄 → MOV 减值（xlsx 附表）
AGE_MOV_PENALTY = ((40, 1), (50, 2), (60, 3), (70, 4), (80, 5))


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


def age_mov_penalty(age) -> int:
    try:
        years = int(age or 0)
    except (TypeError, ValueError):
        years = 0
    penalty = 0
    for limit, value in AGE_MOV_PENALTY:
        if years >= limit:
            penalty = value
    return penalty


def base_mov(str_score: int, dex_score: int, siz_score: int) -> int:
    if str_score > siz_score and dex_score > siz_score:
        return 9
    if str_score < siz_score and dex_score < siz_score:
        return 7
    return 8


def occupation_by_name(name: str):
    for seq, job, low, high, formula, own in OCCUPATIONS:
        if job == name:
            return {"seq": seq, "name": job, "credit_min": low, "credit_max": high,
                    "formula": formula, "own_skills": own}
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
    return any(name.startswith(cat) for cat in SKILL_CATEGORIES)


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


def skill_defaults(dex_score: int) -> dict[str, int]:
    """规则层面每个标准技能的默认基础值；闪避按 DEX/2 派生，不取表里的 0。"""
    defaults = {canonical_skill(name): int(base or 0) for name, base in SKILL_BASE.items()}
    defaults["闪避"] = max(int(dex_score or 0) // 2, 0)
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
        if name == "闪避":
            # 闪避的基础值由敏捷决定，卡上存的值不作为口径
            base = max(dex_score // 2, 0)
        elif base is None:
            base = SKILL_BASE.get(name, 0)
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
    for name, base in skill_defaults(dex_score).items():
        if name in stored:
            continue
        entry = {"base": base, "growth": 0, "occupation": 0, "interest": 0}
        entry["total"] = skill_total(entry)
        skills[name] = entry

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


def validate(data: dict) -> list[str]:
    """建卡约束：属性范围、技能点不超预算、信用评级在职业区间内。"""
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
        info = fin["occupation_info"]
        credit = data.get("credit_rating")
        if credit is not None and str(credit) != "":
            try:
                credit_value = int(credit)
            except (TypeError, ValueError):
                problems.append("信用评级必须是整数")
            else:
                if not (info["credit_min"] <= credit_value <= info["credit_max"]):
                    problems.append(
                        f"信用评级应在 {info['credit_min']}-{info['credit_max']} 之间")
    if fin["interest_spent"] > fin["interest_budget"]:
        problems.append(f"兴趣点超出预算（{fin['interest_spent']}/{fin['interest_budget']}）")
    for name, entry in fin["skills"].items():
        if entry["total"] < 0 or entry["total"] > SKILL_CEILING:
            problems.append(f"技能「{name}」成功率应在 0-{SKILL_CEILING} 之间")
    problems.extend(occupation_choice_problems(data))
    problems.extend(occupational_point_problems(data))
    problems.extend(weapon_problems(data.get("weapons") or []))
    problems.extend(asset_problems(data.get("assets")))
    return problems


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
    return None


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
