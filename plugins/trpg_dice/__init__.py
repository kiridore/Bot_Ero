import re

from core.base import Plugin, NICKNAME
from core.cq import text
from core.logger import logger
from core.utils import register_plugin
from core import character_store as store
from core.trpg import coc as coc_sheet
from core.trpg import party
import core.context as runtime_context

from .dice import parse, _eval_advantage, _eval_disadvantage
from .games import GAME_SYSTEMS, DEFAULT_GAME_SYSTEM
from .rolls import coc_bonus, coc_check, coc_penalty

# COC 奖惩骰：`.r b2`、`.r p1`（独立原子写法）与 `.r 1d100b2`（后缀写法）
BONUS_RE = re.compile(r"^(?:(\d*)d100)?b(\d*)$", re.IGNORECASE)
PENALTY_RE = re.compile(r"^(?:(\d*)d100)?p(\d*)$", re.IGNORECASE)


def _parse_bonus_count(matched) -> int:
    raw = matched.group(2) or "1"
    count = int(raw) if raw.isdigit() else 1
    if count < 1:
        raise ValueError("奖励骰数量必须大于0")
    if count > 10:
        raise ValueError("奖励骰最多 10 颗")
    return count


def _parse_penalty_count(matched) -> int:
    raw = matched.group(2) or "1"
    count = int(raw) if raw.isdigit() else 1
    if count < 1:
        raise ValueError("惩罚骰数量必须大于0")
    if count > 10:
        raise ValueError("惩罚骰最多 10 颗")
    return count


def _skill_value(expr: str) -> int | None:
    """`.r c70` / `.rh c70` 的 COC 技能值；不是该形式返回 None。"""
    matched = re.fullmatch(r"c(\d+)", (expr or "").strip(), re.IGNORECASE)
    return int(matched.group(1)) if matched else None


@register_plugin
class TrpgPlugin(Plugin):
    name = "trpg_dice"
    description = "跑团骰子系统：DND5E / COC 7th 检定、奖惩骰、暗骰"

    PREFIX_RE = re.compile(
        r"^\.(?:rh(?:\s|$)|ra\s|rc\s|r(?:\s|$))",
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
            elif raw.startswith(".ra "):
                self._handle_coc_check(raw[4:], nickname)
            elif raw.startswith(".rc "):
                self._dispatch_check(raw[4:], nickname)
            elif raw.startswith(".r"):
                self._handle_roll(raw, nickname)
        except ValueError as e:
            self._send_with_record(str(e))
        except Exception:
            logger.exception("TRPG 插件处理异常")
            self._send_with_record("指令处理出错，请检查格式")

    def _send_with_record(self, out: str):
        """输出统一出口：先发到当前会话，录制中同时写入跑团记录。"""
        self.api.send_msg(text(out))
        runtime_context.record_bot_message(self.bot_event.group_id, NICKNAME, out)

    # ── 规则系统分发 ──────────────────────────────────────

    def _current_system(self) -> str:
        """本群当前规则（录制中取记录里的规则，未录制取 /跑团 规则 的选择）。"""
        return party.current_rule(self.bot_event.group_id)

    def _rule_name(self) -> str:
        return GAME_SYSTEMS.get(self._current_system(), {}).get("name", self._current_system())

    def _require_rule(self, rule_id: str, hint: str) -> bool:
        if self._current_system() == rule_id:
            return True
        self._send_with_record(f"当前规则是 {self._rule_name()}，{hint}")
        return False

    def _dispatch_check(self, arg: str, nickname: str):
        system = self._current_system()
        if system == "coc7th":
            raise ValueError("当前规则是 COC 7th，属性检定请用 .ra <技能值>")
        cfg = GAME_SYSTEMS.get(system, GAME_SYSTEMS[DEFAULT_GAME_SYSTEM])
        handler = getattr(self, cfg["check_handler"])
        handler(arg, nickname)

    def _handle_coc_check(self, arg: str, nickname: str):
        """.ra <技能值> — COC 7th 技能检定"""
        if not self._require_rule("coc7th", "COC 检定请先由 DM 发送 /跑团 规则 coc7th"):
            return
        text_arg = arg.strip()
        if text_arg.isdigit():
            value = int(text_arg)
        else:
            # 技能名从当前 COC 角色卡取最终成功率
            user_id = self.bot_event.user_id
            char = store.get_current(user_id) if user_id is not None else None
            if not char or (char.get("rules") or "dnd5e") != "coc7th":
                raise ValueError("格式：.ra <技能值或技能名> — 例：.ra 70 / .ra 侦查（需要 COC 角色卡）")
            value = coc_sheet.skill_value(char, text_arg)
            if value is None:
                raise ValueError(f"角色卡里没有技能「{text_arg}」")
        roll, grade = coc_check(value)
        self._send_with_record(f"{nickname}的COC检定 D100={roll} [技能={value}] → {grade}")

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
            self._send_with_record(out)
            return

        # COC 专用形式：c<技能值> 检定、b/p 奖惩骰
        if self._handle_coc_expr(expr, nickname, reason):
            return

        # 角色属性/技能名替换为数值
        resolved, expr_label = self._resolve_character_expr(expr)
        if resolved is None:
            return

        value, detail = parse(resolved)
        out = self._format(nickname, expr_label, detail, value, reason)
        self._send_with_record(out)

    def _handle_coc_expr(self, expr: str, nickname: str, reason: str = "") -> bool:
        """处理 COC 专用表达式；不是 COC 形式返回 False。"""
        skill = _skill_value(expr)
        if skill is not None:
            if not self._require_rule("coc7th", "COC 检定请先由 DM 发送 /跑团 规则 coc7th"):
                return True
            roll, grade = coc_check(skill)
            self._send_with_record(f"{nickname}的COC检定 D100={roll} [技能={skill}] → {grade}")
            return True

        bonus = BONUS_RE.match(expr)
        penalty = PENALTY_RE.match(expr)
        if bonus or penalty:
            if not self._require_rule("coc7th", "奖惩骰请先由 DM 发送 /跑团 规则 coc7th"):
                return True
            if bonus:
                value, detail = coc_bonus(_parse_bonus_count(bonus))
                label = "奖励骰"
            else:
                value, detail = coc_penalty(_parse_penalty_count(penalty))
                label = "惩罚骰"
            self._send_with_record(self._format(nickname, label, detail, value, reason))
            return True
        return False

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
            self._send_with_record("你还没有角色卡，请到网页端创建：\n" + WEB_TRPG_URL)
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
            self._send_with_record("格式：.rc [优势|劣势] <属性|表达式> [豁免]")
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
            self._send_with_record("格式：.rc [优势|劣势] <属性|表达式> [豁免]")
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
            self._send_with_record(out)
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
        self._send_with_record(out)

    # ── 暗骰 ──────────────────────────────────────────

    def _handle_dark_roll(self, raw: str, nickname: str):
        after = raw[3:].lstrip()
        parts = after.split(None, 1)
        expr = parts[0] if parts else ""
        reason = parts[1] if len(parts) > 1 else ""

        group_id = self.bot_event.group_id
        if group_id is None:
            self._send_with_record("暗骰只能在群聊中使用")
            return

        if not expr:
            value, detail = parse("")
            expr_label = "D100"
        elif _skill_value(expr) is not None:
            if not self._require_rule("coc7th", "COC 检定请先由 DM 发送 /跑团 规则 coc7th"):
                return
            skill = _skill_value(expr)
            roll, grade = coc_check(skill)
            value = roll
            expr_label = "COC检定"
            detail = f"D100={roll} [技能={skill}] → {grade}"
        else:
            resolved, expr_label = self._resolve_character_expr(expr)
            if resolved is None:
                return
            value, detail = parse(resolved)

        # Group hint
        self._send_with_record("悄悄掷出骰子")

        # Private result：结果只回私聊，录制中以暗骰标记入档，不在群内出现
        full = self._format(nickname, expr_label, detail, value, reason)
        runtime_context.record_bot_message(group_id, NICKNAME, full, secret=True)
        if self.bot_event.user_id:
            self.api.send_private_msg(text(full))
