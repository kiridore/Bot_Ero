import re

from core.base import Plugin
from core.cq import text
from core.logger import logger
from core.utils import register_plugin
from core import character_store as store
import core.context as runtime_context

from .dice import parse, _eval_advantage, _eval_disadvantage
from .games import GAME_SYSTEMS, DEFAULT_GAME_SYSTEM


@register_plugin
class TrpgPlugin(Plugin):
    name = "trpg_dice"
    description = "跑团骰子系统：DND5E 检定、暗骰（规则可切换）"

    PREFIX_RE = re.compile(
        r"^\.(?:rh(?:\s|$)|rc\s|r(?:\s|$))",
        re.IGNORECASE,
    )

    def match(self, message_type):
        if message_type != "message":
            return False
        message = self.bot_event.message
        if len(message) != 1:
            return False
        seg = message[0]
        if seg.get("type") != "text":
            return False
        msg = seg.get("data", {}).get("text", "").strip()
        return self.PREFIX_RE.match(msg) is not None

    def handle(self):
        try:
            raw = self.bot_event.message[0]["data"]["text"].strip()
            nickname = self._get_nickname()

            if raw.startswith(".rh"):
                self._handle_dark_roll(raw, nickname)
            elif raw.startswith(".rc "):
                self._dispatch_check(raw[4:], nickname)
            elif raw.startswith(".r"):
                self._handle_roll(raw, nickname)
        except ValueError as e:
            self.api.send_msg(text(str(e)))
        except Exception:
            logger.exception("TRPG 插件处理异常")
            self.api.send_msg(text("指令处理出错，请检查格式"))

    # ── 规则系统分发 ──────────────────────────────────────
    # 未来规则切换功能修改 runtime_context.GAME_SYSTEM 即可

    def _current_system(self) -> str:
        return getattr(runtime_context, "GAME_SYSTEM", DEFAULT_GAME_SYSTEM)

    def _dispatch_check(self, arg: str, nickname: str):
        system = self._current_system()
        cfg = GAME_SYSTEMS.get(system, GAME_SYSTEMS[DEFAULT_GAME_SYSTEM])
        handler = getattr(self, cfg["check_handler"])
        handler(arg, nickname)

    def _get_nickname(self):
        sender = self.bot_event.sender
        if sender and isinstance(sender, dict):
            return sender.get("card") or sender.get("nickname") or f"用户{self.bot_event.user_id}"
        return f"用户{self.bot_event.user_id}"

    def _format(self, nickname, expr_label, detail, value, reason=""):
        prefix = f"由于{reason}，" if reason else ""
        return f"{prefix}{nickname}掷出了 {expr_label}={detail}={value}"

    def _handle_roll(self, raw: str, nickname: str):
        after = raw[2:].lstrip()  # strip ".r" and optional space
        parts = after.split(None, 1)
        expr = parts[0] if parts else ""
        reason = parts[1] if len(parts) > 1 else ""

        if not expr:
            # Bare .r → D100
            value, detail = parse("")
            out = self._format(nickname, "D100", detail, value, reason)
            self.api.send_msg(text(out))
            return

        # 角色属性/技能名替换为数值
        resolved, expr_label = self._resolve_character_expr(expr)
        if resolved is None:
            return

        value, detail = parse(resolved)
        out = self._format(nickname, expr_label, detail, value, reason)
        self.api.send_msg(text(out))

    def _resolve_character_expr(self, expr: str):
        """若表达式含角色属性/技能名，替换为数值。返回 (解析后表达式, 显示用原式) 或 (None, None)。"""
        from plugins.trpg_char.character import resolve_expression_values
        from plugins.trpg_char.rules import ATTRIBUTES, SKILLS, SKILL_ALIASES

        names = [n for n in list(ATTRIBUTES) + list(SKILLS) if n in expr]
        aliases = [a for a in SKILL_ALIASES if a in expr]
        if not names and not aliases:
            return expr, expr

        user_id = self.bot_event.user_id
        if user_id is None:
            return None, None
        char = store.get_current(user_id)
        if not char:
            from plugins.trpg_char import WEB_TRPG_URL
            self.api.send_msg(text("你还没有角色卡，请到网页端创建：\n" + WEB_TRPG_URL))
            return None, None

        values = resolve_expression_values(char)
        resolved = expr
        for name in sorted(values, key=len, reverse=True):
            resolved = resolved.replace(name, str(values[name]))
        for alias in aliases:
            resolved = resolved.replace(alias, str(values[SKILL_ALIASES[alias]]))
        return resolved, expr

    # ── DND 5E 检定 ──────────────────────────────────────

    def _handle_dnd_check(self, arg: str, nickname: str):
        """DND d20 检定：.rc [优势|劣势] <属性|表达式> [豁免]"""
        parts = arg.split()
        if not parts:
            self.api.send_msg(text("格式：.rc [优势|劣势] <属性|表达式> [豁免]"))
            return

        is_save = False
        if parts[-1] == "豁免":
            is_save = True
            parts = parts[:-1]

        mode = "normal"
        if parts and parts[0] in ("优势", "劣势"):
            mode = parts[0]
            parts = parts[1:]

        if not parts:
            self.api.send_msg(text("格式：.rc [优势|劣势] <属性|表达式> [豁免]"))
            return

        expr = " ".join(parts)
        resolved, label = self._resolve_character_expr(expr)
        if resolved is None:
            return

        suffix = "豁免" if is_save else "检定"
        mode_str = {"优势": "(优势)", "劣势": "(劣势)", "normal": ""}[mode]
        head = f"{nickname}的{label}{suffix}{mode_str}: "

        # 纯数值修正（属性/技能名已替换，如 2、2+3）
        if not re.search(r"[dbp%#优势劣势]", resolved):
            mod, _ = parse(resolved)
            mod_str = f"+{mod}" if mod >= 0 else str(mod)
            if mode == "优势":
                adv = _eval_advantage(20)
                out = f"{head}d20{mod_str}={adv['detail']}{mod_str}={adv['value'] + mod}"
            elif mode == "劣势":
                adv = _eval_disadvantage(20)
                out = f"{head}d20{mod_str}={adv['detail']}{mod_str}={adv['value'] + mod}"
            else:
                value, detail = parse("d20")
                out = f"{head}d20{mod_str}={detail}{mod_str}={value + mod}"
            self.api.send_msg(text(out))
            return

        # 复杂表达式：d20 + (表达式)
        if mode == "normal":
            value, detail = parse(f"d20+({resolved})")
            out = f"{head}{detail}={value}"
        elif mode == "优势":
            adv = _eval_advantage(20)
            rest_value, rest_detail = parse(f"({resolved})")
            out = f"{head}d20优势={adv['detail']} + {rest_detail}={adv['value'] + rest_value}"
        else:
            adv = _eval_disadvantage(20)
            rest_value, rest_detail = parse(f"({resolved})")
            out = f"{head}d20劣势={adv['detail']} + {rest_detail}={adv['value'] + rest_value}"
        self.api.send_msg(text(out))

    # ── 暗骰 ──────────────────────────────────────────

    def _handle_dark_roll(self, raw: str, nickname: str):
        after = raw[3:].lstrip()
        parts = after.split(None, 1)
        expr = parts[0] if parts else ""
        reason = parts[1] if len(parts) > 1 else ""

        group_id = self.bot_event.group_id
        if group_id is None:
            self.api.send_msg(text("暗骰只能在群聊中使用"))
            return

        if not expr:
            value, detail = parse("")
            expr_label = "D100"
        else:
            resolved, expr_label = self._resolve_character_expr(expr)
            if resolved is None:
                return
            value, detail = parse(resolved)

        # Group hint
        self.api.send_msg(text("悄悄掷出骰子"))

        # Private result
        full = self._format(nickname, expr_label, detail, value, reason)
        if self.bot_event.user_id:
            self.api.send_private_msg(text(full))
