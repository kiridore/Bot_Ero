"""COC 7th 角色卡：派生值、技能点预算与人物卡文本。

建卡逻辑对齐 docs/COC七版人物卡v1.6.1.xlsx：属性手填/掷骰，年龄只影响 MOV（附表口径），
技能 = 基础值 + 成长 + 职业点 + 兴趣点（上限 99），职业点预算按职业公式、兴趣点 = 智力×2，
信用评级受职业区间约束。伤害加值与体格按 STR+SIZ 查表。
"""

from __future__ import annotations

from core.trpg.coc_data import OCCUPATIONS, SKILL_BASE, SKILL_CATEGORIES

SKILL_MAX = 99

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
    return min(total, SKILL_MAX)


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
        if base is None:
            base = SKILL_BASE.get(name, 0)
        merged = {
            "base": int(base or 0),
            "growth": int(entry.get("growth") or 0),
            "occupation": int(entry.get("occupation") or 0),
            "interest": int(entry.get("interest") or 0),
        }
        merged["total"] = skill_total(merged)
        skills[raw_name] = merged

    occupation_spent = sum(entry["occupation"] for entry in skills.values())
    interest_spent = sum(entry["interest"] for entry in skills.values())

    out.update({
        "rules": "coc7th",
        "scores": {
            "力量": str_score, "体质": con_score, "体型": siz_score, "敏捷": dex_score,
            "外貌": app_score, "智力": int_score, "意志": pow_score, "教育": edu_score,
        },
        "hp": max((con_score + siz_score) // 10, 0),
        "mp": max(pow_score // 5, 0),
        "san": max(pow_score, 0),
        "max_san": max(99 - int((data.get("cthulhu_mythos") or 0)), 0),
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


def validate(data: dict) -> list[str]:
    """建卡约束：属性范围、技能点不超预算、信用评级在职业区间内。"""
    problems = []
    fin = finalize(data)
    for attr, value in fin["scores"].items():
        if value and not (1 <= value <= 99):
            problems.append(f"{attr}应在 1-99 之间")
    if fin["occupation_info"] is None:
        problems.append("请选择职业")
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
        if entry["total"] < 0 or entry["total"] > SKILL_MAX:
            problems.append(f"技能「{name}」成功率应在 0-99 之间")
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
    background = data.get("background") or {}
    if isinstance(background, dict):
        traits = background.get("traits") or ""
        if traits:
            lines.append(f"特质：{traits}")
    notes = (data.get("notes") or "").strip()
    if notes:
        lines.append(f"备注：{notes[:80]}")
    return "\n".join(lines)
