import random


def coc_check(value: int):
    if value < 1 or value > 100:
        raise ValueError("技能值应在1~100之间")

    roll = random.randint(1, 100)
    extreme = max(value // 5, 1)
    hard = max(value // 2, 1)

    if roll <= extreme:
        grade = "极限成功"
    elif roll <= hard:
        grade = "困难成功"
    elif roll <= value:
        grade = "常规成功"
    elif roll >= 96:
        grade = "大失败"
    else:
        grade = "失败"

    return roll, grade


def coc_opposed(a_value: int, b_value: int):
    a_roll, a_grade = coc_check(a_value)
    b_roll, b_grade = coc_check(b_value)

    levels = {"大失败": 0, "失败": 1, "常规成功": 2, "困难成功": 3, "极限成功": 4}
    a_level = levels.get(a_grade, 0)
    b_level = levels.get(b_grade, 0)

    if a_level > b_level:
        result = "A胜"
    elif b_level > a_level:
        result = "B胜"
    else:
        if a_roll == b_roll:
            result = "平局"
        elif a_roll < b_roll:
            result = "A胜"
        else:
            result = "B胜"

    return a_roll, a_grade, b_roll, b_grade, result


def dnd_advantage(modifier=0):
    rolls = [random.randint(1, 20), random.randint(1, 20)]
    best = max(rolls)
    total = best + modifier
    return rolls, best, total


def dnd_disadvantage(modifier=0):
    rolls = [random.randint(1, 20), random.randint(1, 20)]
    worst = min(rolls)
    total = worst + modifier
    return rolls, worst, total


def dnd_ability_scores():
    results = []
    for _ in range(6):
        rolls = [random.randint(1, 6) for _ in range(4)]
        rolls.sort(reverse=True)
        kept = rolls[:3]
        results.append((rolls, sum(kept)))
    return results
