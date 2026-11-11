"""跑团数值变动：HP / SAN 与 COC 理智检定。

- `.hp <±值|满> [@目标]`：两套规则通用，扣/加当前 HP
- `.san <±值|满> [@目标]`：COC 专属，扣/加当前 SAN
- `.sc <成功损失>/<失败损失> [@目标]`：COC 理智检定，掷 D100 与当前 SAN 比

改别人的卡需要群内 DM（或超级用户）身份；本次不支持的组合直接拒绝并说明。
"""

import random
import re
from datetime import date

from core.base import Plugin, NICKNAME, SUPER_USER
from core.cq import text
from core.logger import logger
from core.utils import register_plugin
from core import character_store as store
from core.trpg import character as dnd
from core.trpg import coc, party, vitals
import core.context as runtime_context

PREFIX_RE = re.compile(r"^\.(?:hp|san|sc)(?:\s|$)", re.IGNORECASE)
DICE_RE = re.compile(r"^(\d*)d(\d+)([+-]\d+)?$", re.IGNORECASE)
MAX_DICE = 100
MAX_SIDES = 1000


def roll_expression(expr: str):
    """掷 `3` / `1d6` / `2d6+2`；返回 (数值, 明细)。"""
    raw = (expr or "").strip()
    if raw.isdigit():
        return int(raw), raw
    matched = DICE_RE.match(raw)
    if not matched:
        raise ValueError(f"无法解析的损失表达式：{expr}")
    count = int(matched.group(1) or 1)
    sides = int(matched.group(2))
    modifier = int(matched.group(3) or 0)
    if not 1 <= count <= MAX_DICE or not 1 <= sides <= MAX_SIDES:
        raise ValueError("骰子数量或面数超出限制")
    values = [random.randint(1, sides) for _ in range(count)]
    total = sum(values) + modifier
    label = f"{count}d{sides}" if count > 1 else f"d{sides}"
    detail = f"{label}={total}"
    return total, detail


@register_plugin
class TrpgVitalsPlugin(Plugin):
    name = "trpg_vitals"
    description = "跑团数值：.hp 扣/加血量、.san 理智、.sc 理智检定"

    # ── 匹配与分发 ──────────────────────────────────────

    def _first_text(self) -> str:
        for seg in self.bot_event.message:
            if seg.get("type") == "text":
                return seg.get("data", {}).get("text", "").strip()
        return ""

    def _command_parts(self):
        parts = self._first_text().split()
        if not parts or not PREFIX_RE.match(parts[0]):
            return None
        return parts

    def match(self, message_type) -> bool:
        if message_type != "message":
            return False
        return self._command_parts() is not None

    def handle(self):
        try:
            parts = self._command_parts()
            if parts is None:
                return
            cmd = parts[0].lower()
            if cmd == ".hp":
                self._handle_amount("hp", parts[1:])
            elif cmd == ".san":
                self._handle_amount("san", parts[1:])
            else:
                self._handle_san_check(parts[1:])
        except ValueError as exc:
            self.api.send_msg(text(str(exc)))
        except Exception:
            logger.exception("跑团数值指令处理异常")
            self.api.send_msg(text("指令处理出错，请检查格式"))

    # ── 目标与权限 ──────────────────────────────────────

    def _at_target(self) -> str | None:
        for seg in self.bot_event.message:
            if seg.get("type") == "at":
                qq = str(seg.get("data", {}).get("qq", ""))
                if qq and qq != "all":
                    return qq
        return None

    def _is_group_admin(self, group_id) -> bool:
        user_id = str(self.bot_event.user_id or "")
        if user_id.isdigit() and int(user_id) in SUPER_USER:
            return True
        if group_id is None:
            return False
        session = runtime_context.get_recording_session(group_id)
        roles = session.get("roles") if session else None
        if roles is None:
            roles = party.read_pending(group_id)["roles"]
        return roles.get(user_id) == "dm"

    def _resolve_target(self):
        """返回 (目标 user_id, 角色卡)。改他人需要 DM/超管。"""
        sender = str(self.bot_event.user_id or "")
        target = self._at_target() or sender
        if not target:
            raise ValueError("无法识别目标")
        if target != sender and not self._is_group_admin(self.bot_event.group_id):
            raise ValueError("只有 DM 可以修改他人的数值")
        char = store.get_current(target)
        if not char:
            raise ValueError("你还没有角色卡，请到网页端创建" if target == sender
                             else f"{target} 还没有角色卡")
        return target, char

    def _check_rule(self, char: dict) -> str:
        """卡片规则必须与本团规则一致；返回规则 id。"""
        card_rule = char.get("rules") or "dnd5e"
        group_id = self.bot_event.group_id
        if group_id is not None:
            group_rule = party.current_rule(group_id)
            if card_rule != group_rule:
                from core.trpg.game_systems import rule_name
                raise ValueError(
                    f"本团规则是 {rule_name(group_rule)}，目标角色卡是 {rule_name(card_rule)}，"
                    f"请先切换角色卡或让 DM 调整本团规则"
                )
        return card_rule

    def _reply(self, out: str):
        self.api.send_msg(text(out))
        runtime_context.record_bot_message(self.bot_event.group_id, NICKNAME, out)

    # ── .hp / .san ────────────────────────────────────

    def _handle_amount(self, kind: str, args: list):
        if not args:
            raise ValueError("格式：.hp <±值|满> [@目标] 或 .san <±值|满> [@目标]")
        target, char = self._resolve_target()
        rule = self._check_rule(char)
        if kind == "san" and rule != "coc7th":
            raise ValueError("当前角色卡是 DND 5E，没有 SAN 数值（COC 专用指令）")

        raw = args[0]
        if raw in ("满", "滿", "回满"):
            delta = None
        else:
            sign = 1
            body = raw
            if not body or body[0] not in "+-":
                raise ValueError("请带上正负号，例如 .hp -5 / .san +2 / .hp 满")
            sign = -1 if body[0] == "-" else 1
            body = body[1:]
            amount, detail = roll_expression(body)
            delta = sign * amount
            detail = f"{'-' if sign < 0 else '+'}{detail}"

        data = dict(char)
        nickname = self._display_name(target, char)
        if kind == "hp":
            maximum = self._max_hp(data, rule)
            before = vitals.clamp(data.get("current_hp", maximum), maximum)
            after = maximum if delta is None else vitals.clamp(before + delta, maximum)
            data["current_hp"] = after
            label = "HP"
        else:
            maximum = self._max_san(data)
            before = vitals.clamp(data.get("current_san", maximum), maximum)
            after = maximum if delta is None else vitals.clamp(before + delta, maximum)
            data["current_san"] = after
            label = "SAN"

        try:
            store.update_char(target, char["id"], data)
        except ValueError:
            raise ValueError("角色卡写入失败")
        out = f"{nickname}的{vitals.format_change(label, before, after, '' if delta is None else detail)}"
        if delta is None:
            out = f"{nickname}的{label}已回满 → {after}"
        note = self._state_note(kind, after, rule)
        if note:
            out += f"\n· {note}"
        self._reply(out)

    def _max_hp(self, data: dict, rule: str) -> int:
        if rule == "coc7th":
            return int(coc.finalize(data)["hp"])
        return int(dnd.finalize(data)["hp"])

    def _max_san(self, data: dict) -> int:
        return int(coc.finalize(data)["max_san"])

    def _state_note(self, kind: str, value: int, rule: str) -> str:
        if value > 0:
            return ""
        if kind == "san":
            return "SAN 归零：永久疯狂"
        return "HP 归零：昏迷" if rule != "coc7th" else "HP 归零：濒死"

    def _display_name(self, user_id, char: dict) -> str:
        sender = self.bot_event.sender
        if str(self.bot_event.user_id or "") == str(user_id) and sender and isinstance(sender, dict):
            return sender.get("card") or sender.get("nickname") or user_id
        return char.get("char_name") or user_id

    # ── .sc 理智检定 ──────────────────────────────────

    def _handle_san_check(self, args: list):
        if not args or "/" not in args[0]:
            raise ValueError("格式：.sc <成功损失>/<失败损失>，例：.sc 1/1d6")
        target, char = self._resolve_target()
        rule = self._check_rule(char)
        if rule != "coc7th":
            raise ValueError("当前角色卡是 DND 5E，理智检定是 COC 专用指令")

        success_expr, _, fail_expr = args[0].partition("/")
        data = dict(char)
        maximum = self._max_san(data)
        before = vitals.clamp(data.get("current_san", maximum), maximum)
        roll = random.randint(1, 100)
        success = roll <= before
        expr = success_expr if success else fail_expr
        loss, detail = roll_expression(expr or "0")
        after = vitals.clamp(before - loss, maximum)

        data["current_san"] = after
        today = date.today().isoformat()
        accumulated = int(data.get("san_loss_today") or 0) if data.get("san_loss_day") == today else 0
        accumulated += loss
        data["san_loss_day"] = today
        data["san_loss_today"] = accumulated
        try:
            store.update_char(target, char["id"], data)
        except ValueError:
            raise ValueError("角色卡写入失败")

        nickname = self._display_name(target, char)
        lines = [
            f"{nickname}的理智检定 D100={roll} [SAN {before}] → {'成功' if success else '失败'}",
            f"SAN {before} → {after}（{detail if loss else '0'}）",
        ]
        threshold = max(before // 5, 1)
        lines.append(f"· 今日累计损失 {accumulated}，不定时疯狂线 {threshold}"
                     + ("（已超过）" if accumulated > threshold else ""))
        if loss >= 5:
            lines.append("· 一次性损失 ≥5，是否需要灵感检定由 DM 决定")
        if after == 0:
            lines.append("· SAN 归零：永久疯狂")
        self._reply("\n".join(lines))
