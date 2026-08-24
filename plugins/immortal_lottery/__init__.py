"""
仙人彩：周一 00:00–周五 23:59:59（北京时间）下注，周日 20:00 自动开奖。
"""

from __future__ import annotations

import random
import re
from typing import Optional

from core.base import Plugin
from core.cq import at, text
from core.onebot_client import resolve_display_name
from core.utils import register_plugin

from .helpers import (
    _DIGITS4,
    _TIER_RATE_PCT,
    _bets_by_user,
    _count_a,
    _in_betting_window,
    _now_bj,
    _payout_tier,
    _period_key_from_monday,
    _period_monday_for_display,
    _sunday_draw_period_monday,
)


def _name(uid: int) -> str:
    try:
        return resolve_display_name(str(uid))
    except Exception:
        return str(uid)


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
        issue = self.dbmanager.immortal.issue_code(gid, pk)
        st = self.dbmanager.immortal.period_stats(gid, pk)
        c = self.dbmanager.immortal.carry(gid)
        pts = int(st.get("bet_points", 0))
        users = int(st.get("distinct_users", 0))
        bets = int(st.get("bet_count", 0))
        lines = [
            "【仙人彩 · 本期概况】",
            f"期号：{issue}",
            f"周期（周一）起点：{pk}",
            f"本期累计投注：{pts} 积分（{bets} 注，{users} 人参与）",
            f"滚存总奖池：{c} 积分（开奖时并入本期总池）",
        ]
        if bets:
            lines.append(f"本期注单（{bets} 注 / {users} 人）：")
            for uid, digits_list in _bets_by_user(self.dbmanager.immortal.list_bets(gid, pk)):
                lines.append(f"  · {_name(uid)}：{'、'.join(digits_list)}")
        lines += [
            "",
            "下注期：每周一 00:00–周五 23:59（北京时间）",
            "开奖：每周日 20:00 自动开奖",
            "每注 1 积分；每人每天最多 1 注。",
            "中奖按当时总池比例拿走：一等奖 40% / 二等奖 15% / 三等奖 5%；未派发部分全部滚入下期总奖池。",
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
        ok, err = self.dbmanager.immortal.try_place_bet(gid, pk, int(uid), digits, bet_date, 1)
        if not ok:
            self.api.send_msg(at(int(uid)), text(err))
            return
        issue = self.dbmanager.immortal.issue_code(gid, pk)
        rest = self.dbmanager.points.get(uid)
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
        groups = db.immortal.groups_for_draw(pk)
        for gid in groups:
            if db.immortal.has_result(gid, pk):
                continue
            self._run_single_group_draw(gid, pk)

    def _run_single_group_draw(self, group_id: int, period_key: str):
        db = self.dbmanager
        issue = db.immortal.issue_code(group_id, period_key)
        bets = db.immortal.list_bets(group_id, period_key)
        bet_total = len(bets)
        pool = bet_total + db.immortal.carry(group_id)

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

        payouts: list[tuple[int, int]] = []
        pay_detail: list[tuple[int, int, str]] = []
        pool_left = pool
        takes: dict[int, int] = {}
        for a, tier, prize_name in (
            (4, tier4, "一等奖(4A)"),
            (3, tier3, "二等奖(3A)"),
            (2, tier2, "三等奖(2A)"),
        ):
            if not tier:
                continue
            detail, pay, take = _payout_tier(pool_left, tier, _TIER_RATE_PCT[a], prize_name)
            pay_detail.extend(detail)
            payouts.extend(pay)
            takes[a] = take
            pool_left -= take
        new_carry = pool_left

        drawn_at = _now_bj().strftime("%Y-%m-%d %H:%M:%S")
        try:
            ok = db.immortal.finalize_draw(
                group_id,
                period_key,
                winning,
                bet_total,
                drawn_at,
                new_carry,
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
            f"总奖池（本期投注 {bet_total} + 滚存）：{pool} 积分",
            "",
        ]
        for a, tier, prize_name in (
            (4, tier4, "一等奖(4A)"),
            (3, tier3, "二等奖(3A)"),
            (2, tier2, "三等奖(2A)"),
        ):
            rate = _TIER_RATE_PCT[a]
            n = len(tier)
            if n == 0:
                lines.append(f"{prize_name}无人中奖，{rate}% 份额留在总奖池。")
                continue
            take = takes.get(a, 0)
            note = "（池浅不足均分，按下注先后各 1 分至耗尽）" if take < n else ""
            lines.append(f"{prize_name}：{n} 注，按当时总池 {rate}% 拿走 {take} 积分，人均约 {take // n}{note}。")
        lines.append(f"派发后剩余 {new_carry} 积分滚入下期总奖池。")

        if bets:
            by_user = _bets_by_user(bets)
            lines.append("")
            lines.append(f"本期注单（{bet_total} 注 / {len(by_user)} 人）：")
            for uid, digits_list in by_user:
                lines.append(f"  · {_name(uid)}：{'、'.join(digits_list)}")

        if pay_detail:
            lines.append("")
            lines.append("中奖发放（整数积分；余数滚存；不足每人 1 分时按下注顺序）：")
            for uid, amt, label in pay_detail:
                lines.append(f"  · {_name(uid)} {label} → {amt} 积分")

        msg = "\n".join(lines)
        self.api.call_api("send_group_msg", {"group_id": int(group_id), "message": (text(msg),)})