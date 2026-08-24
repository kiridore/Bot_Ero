"""仙人彩：开奖与周期相关纯函数（仅依赖 stdlib）。"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

_BJ = ZoneInfo("Asia/Shanghai")
_DIGITS4 = re.compile(r"^[0-9]{4}$")


def _now_bj() -> datetime:
    return datetime.now(_BJ)


def _period_monday_for_display(d: date) -> date:
    """自然周内的周一（周日归属到刚过去的周一为起点的周期）。"""
    wd = d.weekday()
    if wd == 6:
        return d - timedelta(days=6)
    if wd == 5:
        return d - timedelta(days=5)
    return d - timedelta(days=wd)


def _period_key_from_monday(mon: date) -> str:
    return mon.strftime("%Y-%m-%d")


def _in_betting_window(now_bj: datetime) -> bool:
    wd = now_bj.weekday()
    if wd > 4:
        return False
    if wd < 4:
        return True
    t = now_bj.time().replace(tzinfo=None)
    return t <= time(23, 59, 59)


def _sunday_draw_period_monday(sunday: date) -> date:
    return sunday - timedelta(days=6)


def _count_a(secret: str, guess: str) -> int:
    return sum(1 for i in range(4) if secret[i] == guess[i])


# 单一总奖池下各奖级的「拿走比例」：开奖按 4A → 3A → 2A 逐级从当前池派发，
# 池单调缩小且比例递减，保证高奖级单注奖金恒大于低奖级（不会倒挂）。
_TIER_RATE_PCT = {4: 40, 3: 15, 2: 5}


def _payout_tier(
    pool: int,
    ordered_winners: list[tuple[int, str]],
    rate_pct: int,
    prize_name: str,
) -> tuple[list[tuple[int, int, str]], list[tuple[int, int]], int]:
    """
    单奖级按当时总池比例派发：n 注合计拿走 pool * (1-(1-r)^n)，奖级内均分，
    均分余数留池。只派发整数积分；合计不足 n 分时按下注先后各发 1 分至耗尽。
    返回 (展示明细, 实际加分的 (uid, amt) 列表, 实际派发总额)。
    """
    n = len(ordered_winners)
    if n == 0 or pool <= 0:
        return [], [], 0
    total_take = pool * (100 ** n - (100 - rate_pct) ** n) // 100 ** n
    detail: list[tuple[int, int, str]] = []
    payouts: list[tuple[int, int]] = []

    if total_take < n:
        for i, (uid, dg) in enumerate(ordered_winners):
            amt = 1 if i < total_take else 0
            detail.append((uid, amt, f"{prize_name} {dg}"))
            if amt > 0:
                payouts.append((uid, amt))
        return detail, payouts, total_take

    base = total_take // n
    for uid, dg in ordered_winners:
        detail.append((uid, base, f"{prize_name} {dg}"))
        if base > 0:
            payouts.append((uid, base))
    return detail, payouts, base * n


def _bets_by_user(bets: list[tuple]) -> list[tuple[int, list[str]]]:
    """按人聚合注单：[(uid, [号码, ...])]，人按首次下注顺序、号码保留下注先后。"""
    order: list[int] = []
    grouped: dict[int, list[str]] = {}
    for _bid, uid, dg in bets:
        if uid not in grouped:
            grouped[uid] = []
            order.append(uid)
        grouped[uid].append(dg)
    return [(uid, grouped[uid]) for uid in order]