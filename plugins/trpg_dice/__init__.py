import re

from core.base import Plugin
from core.cq import text
from core.logger import logger
from core.utils import register_plugin

from .dice import parse, format_roll
from .rolls import (
    coc_check,
    coc_opposed,
    dnd_advantage,
    dnd_disadvantage,
    dnd_ability_scores,
)


@register_plugin
class TrpgPlugin(Plugin):
    name = "trpg_dice"
    description = "跑团骰子系统：DND5e/COC7th 检定、优势劣势、属性投点"

    PREFIX_RE = re.compile(
        r"^\.(?:rcb\s|rc\s|rh(?:\s|$)|ra\s|rd\s|r\s)",
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
            msg = self.bot_event.message[0]["data"]["text"].strip()

            if msg.startswith(".rcb "):
                self._handle_coc_opposed(msg[5:].strip())
            elif msg.startswith(".rc "):
                self._handle_coc_check(msg[4:].strip())
            elif msg.startswith(".rh"):
                self._handle_roll_ability()
            elif msg.startswith(".ra "):
                self._handle_advantage(msg[4:].strip())
            elif msg.startswith(".rd "):
                self._handle_disadvantage(msg[4:].strip())
            elif msg.startswith(".r "):
                self._handle_roll_expr(msg[2:].strip())
        except Exception:
            logger.exception("TRPG 插件处理异常")
            self.api.send_msg(text("指令处理出错，请检查格式"))

    def _handle_roll_expr(self, expr):
        dr = parse(expr)
        raw, total, desc = dr.roll()
        label = f"{dr.count}d{dr.sides}"
        if dr.keep:
            label += f"k{dr.keep}"
        if dr.modifier:
            label += f"{'+' if dr.modifier > 0 else ''}{dr.modifier}"

        out = f"{expr} = {label}\n{desc}\n合计: {total}"
        self.api.send_msg(text(out))

    def _handle_advantage(self, expr):
        try:
            mod = int(expr) if expr.lstrip("+-").isdigit() else 0
            expr_parsed = expr
        except ValueError:
            mod = 0
            expr_parsed = expr

        if expr_parsed.lstrip("+-").isdigit():
            dr = type("obj", (), {"sides": 20, "count": 1, "keep": None, "modifier": int(expr_parsed)})()
            rolls, best, total = dnd_advantage(int(expr_parsed))
            mod_str = f"{'+' if int(expr_parsed) > 0 else ''}{int(expr_parsed)}"
            out = f"[优势] d20{mod_str}\n({rolls[0]}, {rolls[1]}) 取高 = {best}\n合计: {total}"
        else:
            try:
                dr = parse(expr_parsed)
            except ValueError:
                dr = parse(f"d20+{expr_parsed}")
            if dr.sides == 20:
                rolls, best, total = dnd_advantage(dr.modifier)
                mod_str = f"{'+' if dr.modifier > 0 else ''}{dr.modifier}"
                out = f"[优势] d20{mod_str}\n({rolls[0]}, {rolls[1]}) 取高 = {best}\n合计: {total}"
            else:
                self._handle_roll_expr(expr_parsed)
                return

        self.api.send_msg(text(out))

    def _handle_disadvantage(self, expr):
        try:
            mod = int(expr) if expr.lstrip("+-").isdigit() else 0
            expr_parsed = expr
        except ValueError:
            mod = 0
            expr_parsed = expr

        if expr_parsed.lstrip("+-").isdigit():
            rolls, worst, total = dnd_disadvantage(int(expr_parsed))
            mod_str = f"{'+' if int(expr_parsed) > 0 else ''}{int(expr_parsed)}"
            out = f"[劣势] d20{mod_str}\n({rolls[0]}, {rolls[1]}) 取低 = {worst}\n合计: {total}"
        else:
            try:
                dr = parse(expr_parsed)
            except ValueError:
                dr = parse(f"d20+{expr_parsed}")
            if dr.sides == 20:
                rolls, worst, total = dnd_disadvantage(dr.modifier)
                mod_str = f"{'+' if dr.modifier > 0 else ''}{dr.modifier}"
                out = f"[劣势] d20{mod_str}\n({rolls[0]}, {rolls[1]}) 取低 = {worst}\n合计: {total}"
            else:
                self._handle_roll_expr(expr_parsed)
                return

        self.api.send_msg(text(out))

    def _handle_coc_check(self, arg):
        try:
            value = int(arg)
        except ValueError:
            self.api.send_msg(text("格式：.rc <技能值>  — 例：.rc 70"))
            return

        roll, grade = coc_check(value)
        out = f"[COC检定] D100={roll} [技能={value}]\n结果: {grade}"
        self.api.send_msg(text(out))

    def _handle_coc_opposed(self, arg):
        parts = arg.split()
        if len(parts) != 2:
            self.api.send_msg(text("格式：.rcb <A值> <B值>  — 例：.rcb 60 50"))
            return
        try:
            a_val = int(parts[0])
            b_val = int(parts[1])
        except ValueError:
            self.api.send_msg(text("技能值必须为数字"))
            return

        a_roll, a_grade, b_roll, b_grade, result = coc_opposed(a_val, b_val)
        out = (
            f"[对抗检定]\n"
            f"A: D100={a_roll} [{a_val}] → {a_grade}\n"
            f"B: D100={b_roll} [{b_val}] → {b_grade}\n"
            f"结果: {result}"
        )
        self.api.send_msg(text(out))

    def _handle_roll_ability(self):
        scores = dnd_ability_scores()
        lines = ["[DND属性投点] (4d6k3)"]
        total = 0
        for i, (rolls, score) in enumerate(scores, 1):
            rolls_str = ", ".join(str(r) for r in rolls)
            lines.append(f"{i}: {score:>2}  ({rolls_str})")
            total += score
        lines.append(f"合计: {total}")
        self.api.send_msg(text("\n".join(lines)))
