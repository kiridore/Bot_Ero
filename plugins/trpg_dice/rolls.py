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


def coc_bonus(count: int):
    ten_dice = [random.randint(0, 9) for _ in range(count)]
    base = random.randint(1, 100)
    tens = [str(d) for d in ten_dice]
    all_tens = [base % 10] + ten_dice
    best = max(all_tens)
    result = (base // 10) * 10 + best
    if result > 100:
        result = 100
    detail = f"D100={base}, 奖励 {' '.join(tens)}"
    return result, detail


def coc_penalty(count: int):
    ten_dice = [random.randint(0, 9) for _ in range(count)]
    base = random.randint(1, 100)
    tens = [str(d) for d in ten_dice]
    all_tens = [base % 10] + ten_dice
    worst = min(all_tens)
    result = (base // 10) * 10 + worst
    if result > 100:
        result = 100
    detail = f"D100={base}, 惩罚 {' '.join(tens)}"
    return result, detail
