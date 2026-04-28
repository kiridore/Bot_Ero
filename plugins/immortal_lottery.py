"""
仙人彩：周一 00:00–周五 23:59:59（北京时间）下注，周日 20:00 自动开奖。
"""

from __future__ import annotations

import random
import re
from datetime import date, datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from core.base import Plugin
from core.cq import at, text
from core.utils import register_plugin

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


@register_plugin
class ImmortalLotteryPlugin(Plugin):
    name = "immortal_lottery"
    description = "仙人彩：四位数竞猜，周中下注、周日开奖，积分奖池与滚存。"

    _last_draw_slot: Optional[str] = None

    def _draw_heartbeat_match(self) -> bool:
        if self.bot_event.post_type != "meta_event":
            return False
        now = _now_bj()
        if now.weekday() != 6 or now.hour != 20 or now.minute >= 5:
            return False
        key = f"immortal_draw_{now.date().isoformat()}"
        if ImmortalLotteryPlugin._last_draw_slot == key:
            return False
        ImmortalLotteryPlugin._last_draw_slot = key
        return True

    def match(self, event_type: str) -> bool:
        if event_type == "meta":
            return self._draw_heartbeat_match()
        if self.bot_event.post_type != "message":
            return False
        if not self.bot_event.message or self.bot_event.message[0].get("type") != "text":
            return False
        raw = self.bot_event.message[0]["data"]["text"].strip()
        if raw.startswith("／"):
            raw = "/" + raw[1:]
        if raw.startswith("/仙人彩"):
            return True
        if re.match(r"^下注\s+", raw):
            return True
        return False

    def _parse_command(self) -> tuple[str, str]:
        raw = self.bot_event.message[0]["data"]["text"].strip()
        if raw.startswith("／"):
            raw = "/" + raw[1:]
        if raw.startswith("/仙人彩"):
            rest = raw[len("/仙人彩") :].strip()
            return "xianren", rest
        m = re.match(r"^下注\s+(.+)$", raw)
        if m:
            return "bet", m.group(1).strip()
        return "", ""

    def handle(self):
        if self.bot_event.post_type == "meta_event":
            self._handle_draw_tick()
            return
        if self.bot_event.group_id is None:
            self.api.send_msg(text("仙人彩请在群聊中使用。"))
            return
        kind, rest = self._parse_command()
        if not kind:
            return
        digits_part = re.sub(r"\s+", "", rest)
        if not digits_part:
            self._send_pool_info()
            return
        if not _DIGITS4.match(digits_part):
            self.api.send_msg(
                text("请发送四位数字（每位 0–9，可重复），例如：/仙人彩 1234 或 下注 0420")
            )
            return
        self._place_bet(digits_part)

    def _current_period_key(self) -> str:
        d = _now_bj().date()
        mon = _period_monday_for_display(d)
        return _period_key_from_monday(mon)

    def _send_pool_info(self):
        gid = int(self.bot_event.group_id)
        pk = self._current_period_key()
        issue = self.dbmanager.immortal_lottery_get_or_create_issue_code(gid, pk)
        st = self.dbmanager.immortal_lottery_period_stats(gid, pk)
        c4, c3, c2 = self.dbmanager.immortal_lottery_get_carry(gid)
        pts = int(st.get("bet_points", 0))
        users = int(st.get("distinct_users", 0))
        bets = int(st.get("bet_count", 0))
        lines = [
            "【仙人彩 · 本期概况】",
            f"期号：{issue}",
            f"周期（周一）起点：{pk}",
            f"本期累计投注：{pts} 积分（{bets} 注，{users} 人参与）",
            f"滚存奖池：一等奖 {c4} / 二等奖 {c3} / 三等奖 {c2}",
            "",
            "下注期：每周一 00:00–周五 23:59（北京时间）",
            "开奖：每周日 20:00 自动开奖",
            "每注 1 积分；每人每天最多 1 注。",
            "发送 /仙人彩 四位数字 或 下注 四位数字 参与。",
        ]
        self.api.send_msg(text("\n".join(lines)))

    def _place_bet(self, digits: str):
        if not _in_betting_window(_now_bj()):
            self.api.send_msg(text("当前不在下注时间内（周一至周五 23:59 北京时间）。"))
            return
        uid = self.bot_event.user_id
        if uid is None:
            return
        gid = int(self.bot_event.group_id)
        pk = self._current_period_key()
        bet_date = _now_bj().strftime("%Y-%m-%d")
        ok, err = self.dbmanager.immortal_lottery_try_place_bet(gid, pk, int(uid), digits, bet_date, 1)
        if not ok:
            self.api.send_msg(at(int(uid)), text(err))
            return
        issue = self.dbmanager.immortal_lottery_get_or_create_issue_code(gid, pk)
        rest = self.dbmanager.get_user_point(uid)
        self.api.send_msg(
            at(int(uid)),
            text(
                f"下注成功：{digits}\n期号：{issue}（周期周一 {pk}）\n已扣 1 积分，当前积分：{rest}"
            ),
        )

    def _handle_draw_tick(self):
        now = _now_bj()
        sun = now.date()
        mon = _sunday_draw_period_monday(sun)
        pk = _period_key_from_monday(mon)
        db = self.dbmanager
        groups = db.immortal_lottery_groups_for_period_draw(pk)
        for gid in groups:
            if db.immortal_lottery_has_result(gid, pk):
                continue
            self._run_single_group_draw(gid, pk)

    def _run_single_group_draw(self, group_id: int, period_key: str):
        db = self.dbmanager
        issue = db.immortal_lottery_get_or_create_issue_code(group_id, period_key)
        bets = db.immortal_lottery_list_bets(group_id, period_key)
        bet_total = len(bets)
        p1 = bet_total * 60 // 100
        p2 = bet_total * 25 // 100
        p3 = bet_total - p1 - p2
        c4, c3, c2 = db.immortal_lottery_get_carry(group_id)
        pool_4 = c4 + p1
        pool_3 = c3 + p2
        pool_2 = c2 + p3

        winning = "".join(str(random.randint(0, 9)) for _ in range(4))

        tier4: list[tuple[int, str]] = []
        tier3: list[tuple[int, str]] = []
        tier2: list[tuple[int, str]] = []
        for _bid, uid, dg in bets:
            a = _count_a(winning, dg)
            if a == 4:
                tier4.append((uid, dg))
            elif a == 3:
                tier3.append((uid, dg))
            elif a == 2:
                tier2.append((uid, dg))

        nc4 = len(tier4)
        nc3 = len(tier3)
        nc2 = len(tier2)

        payouts: list[tuple[int, int]] = []
        pay_detail: list[tuple[int, int, str]] = []
        rem4 = rem3 = rem2 = 0
        paid4 = paid3 = paid2 = 0

        if nc4 == 0:
            new_c4 = pool_4
        elif pool_4 <= 0:
            new_c4 = 0
        else:
            d4, p4, rem4 = _allocate_tier_pool(pool_4, tier4, "一等奖(4A)")
            pay_detail.extend(d4)
            payouts.extend(p4)
            paid4 = sum(a for _u, a in p4)
            new_c4 = rem4

        if nc3 == 0:
            new_c3 = pool_3
        elif pool_3 <= 0:
            new_c3 = 0
        else:
            d3, p3, rem3 = _allocate_tier_pool(pool_3, tier3, "二等奖(3A)")
            pay_detail.extend(d3)
            payouts.extend(p3)
            paid3 = sum(a for _u, a in p3)
            new_c3 = rem3

        if nc2 == 0:
            new_c2 = pool_2
        elif pool_2 <= 0:
            new_c2 = 0
        else:
            d2, p2, rem2 = _allocate_tier_pool(pool_2, tier2, "三等奖(2A)")
            pay_detail.extend(d2)
            payouts.extend(p2)
            paid2 = sum(a for _u, a in p2)
            new_c2 = rem2

        drawn_at = _now_bj().strftime("%Y-%m-%d %H:%M:%S")
        try:
            ok = db.immortal_lottery_finalize_draw(
                group_id,
                period_key,
                winning,
                bet_total,
                drawn_at,
                new_c4,
                new_c3,
                new_c2,
                payouts,
            )
        except Exception:
            return
        if not ok:
            return

        lines = [
            "【仙人彩 · 开奖】",
            f"期号：{issue}",
            f"本期周期（周一）：{period_key}",
            f"开奖号码：{winning}",
            f"本期投注：{bet_total} 积分",
            f"各奖级池（本期分成 + 滚存）：一等奖 {pool_4} / 二等奖 {pool_3} / 三等奖 {pool_2}",
            "",
        ]
        if nc4 == 0:
            lines.append(f"一等奖无人中奖，{pool_4} 积分滚入下期一等奖池。")
        else:
            extra4: list[str] = []
            if pool_4 > 0 and pool_4 < nc4:
                extra4.append("奖池不足每人 1 分，已按下注先后各发 1 分至耗尽")
            if rem4 > 0:
                extra4.append(f"均分余数 {rem4} 分滚入下期一等奖池")
            line4 = f"一等奖(4A)：{nc4} 注，奖池 {pool_4}，实际派发 {paid4} 积分"
            if extra4:
                line4 += "（" + "；".join(extra4) + "）"
            lines.append(line4 + "。")
        if nc3 == 0:
            lines.append(f"二等奖无人中奖，{pool_3} 积分滚入下期二等奖池。")
        else:
            extra3: list[str] = []
            if pool_3 > 0 and pool_3 < nc3:
                extra3.append("奖池不足每人 1 分，已按下注先后各发 1 分至耗尽")
            if rem3 > 0:
                extra3.append(f"均分余数 {rem3} 分滚入下期二等奖池")
            line3 = f"二等奖(3A)：{nc3} 注，奖池 {pool_3}，实际派发 {paid3} 积分"
            if extra3:
                line3 += "（" + "；".join(extra3) + "）"
            lines.append(line3 + "。")
        if nc2 == 0:
            lines.append(f"三等奖无人中奖，{pool_2} 积分滚入下期三等奖池。")
        else:
            extra2: list[str] = []
            if pool_2 > 0 and pool_2 < nc2:
                extra2.append("奖池不足每人 1 分，已按下注先后各发 1 分至耗尽")
            if rem2 > 0:
                extra2.append(f"均分余数 {rem2} 分滚入下期三等奖池")
            line2 = f"三等奖(2A)：{nc2} 注，奖池 {pool_2}，实际派发 {paid2} 积分"
            if extra2:
                line2 += "（" + "；".join(extra2) + "）"
            lines.append(line2 + "。")

        if pay_detail:
            lines.append("")
            lines.append("中奖发放（整数积分；余数滚存；不足每人 1 分时按下注顺序）：")
            for _uid, amt, label in pay_detail:
                lines.append(f"  · {label} → {amt} 积分")

        msg = "\n".join(lines)
        self.api.call_api("send_group_msg", {"group_id": int(group_id), "message": (text(msg),)})
