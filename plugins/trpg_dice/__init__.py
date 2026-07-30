import re

from core.base import Plugin
from core.cq import text
from core.logger import logger
from core.utils import register_plugin

from .dice import parse
from .rolls import coc_check


@register_plugin
class TrpgPlugin(Plugin):
    name = "trpg_dice"
    description = "跑团骰子系统：DND5e/COC7th 检定、奖惩骰、暗骰"

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
                self._handle_coc_check(raw[4:], nickname)
            elif raw.startswith(".r"):
                self._handle_roll(raw, nickname)
        except ValueError as e:
            self.api.send_msg(text(str(e)))
        except Exception:
            logger.exception("TRPG 插件处理异常")
            self.api.send_msg(text("指令处理出错，请检查格式"))

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

        if expr.startswith("c"):
            try:
                skill = int(expr[1:])
            except ValueError:
                raise ValueError("格式：.r c<技能值> — 例：.r c70")
            roll, grade = coc_check(skill)
            out = f"{nickname}的COC检定 D100={roll} [技能={skill}] → {grade}"
            self.api.send_msg(text(out))
            return

        value, detail = parse(expr)
        expr_label = expr.replace("优势", "优势").replace("劣势", "劣势")
        out = self._format(nickname, expr_label, detail, value, reason)
        self.api.send_msg(text(out))

    def _handle_coc_check(self, arg: str, nickname: str):
        arg = arg.strip()
        try:
            value = int(arg)
        except ValueError:
            self.api.send_msg(text("格式：.ra <技能值>  — 例：.ra 70"))
            return

        roll, grade = coc_check(value)
        out = f"{nickname}的COC检定 D100={roll} [技能={value}] → {grade}"
        self.api.send_msg(text(out))

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
        elif expr.startswith("c"):
            try:
                skill = int(expr[1:])
            except ValueError:
                raise ValueError("格式：.rh c<技能值> — 例：.rh c70")
            roll, grade = coc_check(skill)
            expr_label = f"c{skill}"
            detail = f"COC检定 D100={roll}"
            value = roll
        else:
            value, detail = parse(expr)
            expr_label = expr.replace("优势", "优势").replace("劣势", "劣势")

        # Group hint
        self.api.send_msg(text("悄悄掷出骰子"))

        # Private result
        full = self._format(nickname, expr_label, detail, value, reason)
        if self.bot_event.user_id:
            self.api.send_private_msg(text(full))
