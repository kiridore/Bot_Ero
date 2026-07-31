from . import rules
from .rules import ATTRIBUTES, RACES, CLASSES, SKILLS


STEP_METHOD = 0
STEP_SCORES = 1
STEP_SKILLS = 2
STEP_INFO = 3
STEP_DONE = 4


def start() -> dict:
    return {"step": STEP_METHOD, "data": {}}


def prompt(state: dict) -> str:
    """生成当前步骤的提示文本。"""
    step = state["step"]
    data = state["data"]

    if step == STEP_METHOD:
        return (
            "第1步：选择属性生成方式\n"
            "  1. 标准购点法（27点）\n"
            "  2. 4d6k3 掷骰法（由机器人掷出6组属性）\n"
            "  3. 标准数组（15, 14, 13, 12, 10, 8）\n"
            "回复 1、2 或 3"
        )

    if step == STEP_SCORES:
        method = data.get("method")
        if method == 1:
            cost = " | ".join(f"{v}={rules.POINT_BUY_COST[v]}" for v in sorted(rules.POINT_BUY_COST))
            return (
                f"第2步：分配属性（标准购点，预算 {rules.POINT_BUY_BUDGET} 点）\n"
                f"购点表: {cost}\n"
                f"按顺序输入 力量 敏捷 体质 智力 感知 魅力 的属性值，空格分隔\n"
                f"例：15 14 13 12 10 8"
            )
        if method == 2:
            values = data.get("rolled_scores", [])
            vals = ", ".join(str(v) for v in values)
            return (
                f"第2步：分配属性（掷骰结果: {vals}）\n"
                f"按顺序输入 力量 敏捷 体质 智力 感知 魅力 对应的值，空格分隔\n"
                f"例：15 12 13 8 10 14"
            )
        return (
            f"第2步：分配属性（标准数组 {', '.join(map(str, rules.STANDARD_ARRAY))}）\n"
            f"按顺序输入 力量 敏捷 体质 智力 感知 魅力 对应的值，空格分隔\n"
            f"例：15 14 13 12 10 8"
        )

    if step == STEP_SKILLS:
        count = data.get("skill_count", 2)
        lines = [f"第3步：选择技能熟练（可选，本职业默认 {count} 项，回复「跳过」可跳过）"]
        lines += [f"  {i}. {name}" for i, name in enumerate(SKILLS, 1)]
        lines.append("回复编号或技能名，多项用空格分隔（例：3 7 或 巧手 洞悉）")
        return "\n".join(lines)

    if step == STEP_INFO:
        return (
            "第4步：输入角色基本信息\n"
            "格式：<角色名> <种族> <职业>（空格分隔，种族/职业可自定义任意文本）\n"
            f"常见种族：{'/'.join(RACES)}\n"
            f"常见职业：{'/'.join(CLASSES)}\n"
            "例：艾伦 精灵 法师"
        )

    return ""


def handle_reply(state: dict, reply: str) -> tuple[str, bool, dict | None]:
    """处理用户回复。返回 (消息文本, 是否完成/放弃, 最终角色数据或None)。"""
    step = state["step"]
    data = state["data"]
    reply = reply.strip()

    if reply == "退出":
        return "已放弃角色创建", True, None

    if step == STEP_METHOD:
        if reply not in ("1", "2", "3"):
            return "请输入 1、2 或 3", False, None
        method = int(reply)
        data["method"] = method
        if method == 2:
            data["rolled_scores"] = _roll_scores()
        return _advance(state)

    if step == STEP_SCORES:
        scores = _parse_scores(reply)
        if not scores:
            return "请输入 6 个数字，空格分隔", False, None
        if data.get("method") == 1:
            if any(v not in rules.POINT_BUY_COST for v in scores):
                return f"购点法属性值必须在 {min(rules.POINT_BUY_COST)}~{max(rules.POINT_BUY_COST)} 之间", False, None
            cost = sum(rules.POINT_BUY_COST[v] for v in scores)
            if cost > rules.POINT_BUY_BUDGET:
                return f"属性总花费 {cost} 点，超过预算 {rules.POINT_BUY_BUDGET}", False, None
        if data.get("method") == 2:
            if sorted(scores) != sorted(data.get("rolled_scores", [])):
                return "属性值必须等于掷骰结果（可调换顺序）", False, None
        if data.get("method") == 3:
            if sorted(scores) != sorted(rules.STANDARD_ARRAY):
                return "属性值必须为 15 14 13 12 10 8（可调换顺序）", False, None
        data["scores"] = {attr: v for attr, v in zip(ATTRIBUTES, scores)}
        return _advance(state)

    if step == STEP_SKILLS:
        if reply in ("跳过", "跳过。"):
            data["proficient_skills"] = []
        else:
            chosen = _match_skills(reply, data.get("skill_count", 2))
            if chosen is None:
                return "技能选择无效，请重新选择（回复「跳过」可跳过）", False, None
            data["proficient_skills"] = chosen
        return _advance(state)

    if step == STEP_INFO:
        parts = reply.split()
        if not parts:
            return "请输入 角色名 种族 职业", False, None
        data["char_name"] = parts[0]
        data["race"] = parts[1] if len(parts) > 1 else "未知"
        data["class_name"] = parts[2] if len(parts) > 2 else "未知"
        if len(data["char_name"]) > 30:
            return "角色名过长（最多30字）", False, None
        state["step"] = STEP_DONE
        char_data = _build_char_data(data)
        return "角色创建完成！\n" + char_data.get("_sheet", ""), True, char_data

    return "", False, None


def _advance(state: dict) -> tuple[str, bool, dict | None]:
    state["step"] += 1
    p = prompt(state)
    return p, False, None


def _match_skills(reply: str, max_count: int) -> list | None:
    parts = reply.replace("，", " ").split()
    names = list(SKILLS.keys())
    chosen = []
    for p in parts:
        if p.isdigit():
            idx = int(p)
            if 1 <= idx <= len(names):
                chosen.append(names[idx - 1])
            else:
                return None
        else:
            if p in SKILLS and p not in chosen:
                chosen.append(p)
            else:
                return None
    if not chosen or len(chosen) > max_count:
        return None
    return chosen


def _parse_scores(reply: str) -> list[int] | None:
    parts = reply.replace("，", " ").replace(",", " ").split()
    if len(parts) != 6:
        return None
    try:
        scores = [int(p) for p in parts]
    except ValueError:
        return None
    if any(s < 1 or s > 30 for s in scores):
        return None
    return scores


def _roll_scores() -> list[int]:
    import random
    scores = []
    for _ in range(6):
        rolls = sorted([random.randint(1, 6) for _ in range(4)], reverse=True)
        scores.append(sum(rolls[:3]))
    return scores


def _build_char_data(data: dict) -> dict:
    from . import character
    scores = data["scores"]
    char_data = {
        "char_name": data["char_name"],
        "race": data["race"],
        "class_name": data["class_name"],
        "level": 1,
        "str_score": scores["力量"],
        "dex_score": scores["敏捷"],
        "con_score": scores["体质"],
        "int_score": scores["智力"],
        "wis_score": scores["感知"],
        "cha_score": scores["魅力"],
        "proficient_skills": data.get("proficient_skills", []),
        "notes": "",
        "hp": 0,
        "ac": 0,
    }
    finalized = character.finalize(char_data)
    char_data["hp"] = finalized["hp"]
    char_data["ac"] = finalized["ac"]
    char_data["_sheet"] = character.format_sheet(char_data)
    return char_data
