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


def _allocate_tier_pool(
    pool: int,
    ordered_winners: list[tuple[int, str]],
    prize_name: str,
) -> tuple[list[tuple[int, int, str]], list[tuple[int, int]], int]:
    """
    只派发整数积分；无法整除的余数滚入该奖级下期池。
    若奖池不足以使每位中奖注至少分到 1 分，则按下注先后各发 1 分直至耗尽。
    返回 (展示明细, 实际加分的 (uid, amt) 列表, 滚入下期该奖级的余数)。
    """
    n = len(ordered_winners)
    if n == 0:
        return [], [], pool
    if pool <= 0:
        return [], [], 0

    detail: list[tuple[int, int, str]] = []
    payouts: list[tuple[int, int]] = []

    if pool < n:
        for i, (uid, dg) in enumerate(ordered_winners):
            amt = 1 if i < pool else 0
            label = f"{prize_name} {dg}"
            detail.append((uid, amt, label))
            if amt > 0:
                payouts.append((uid, amt))
        return detail, payouts, 0

    base = pool // n
    rem = pool % n
    for uid, dg in ordered_winners:
        label = f"{prize_name} {dg}"
        detail.append((uid, base, label))
        if base > 0:
            payouts.append((uid, base))
    return detail, payouts, rem