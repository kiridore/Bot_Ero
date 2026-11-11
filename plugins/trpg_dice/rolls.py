"""COC 7th 检定：技能检定成功等级与奖励/惩罚骰。

从 git 历史（提交 3dae681 前）恢复，行为保持不变：技能值 1~100，D100 对比
极限（技能/5）、困难（技能/2）、常规（技能）判定成功等级；大成功 01；大失败按规则
（技能 ≥50 只有 100，<50 为 96-100）。技能可因幕间成长超过 100。
"""

import random


def coc_check(value: int):
    if value < 1 or value > 199:
        raise ValueError("技能值应在1~199之间")

    roll = random.randint(1, 100)
    extreme = max(value // 5, 1)
    hard = max(value // 2, 1)

    fumble = (roll == 100) if value >= 50 else (roll >= 96)
    if roll == 1:
        grade = "大成功"
    elif fumble:
        grade = "大失败"
    elif roll <= extreme:
        grade = "极限成功"
    elif roll <= hard:
        grade = "困难成功"
    elif roll <= value:
        grade = "常规成功"
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
