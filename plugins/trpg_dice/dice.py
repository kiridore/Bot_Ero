import random
import re

_DICE_RE = re.compile(
    r"^(\d+)?d(\d+|%|f)"           # [count]d<sides|%|F>
    r"(?:k([lh])?(\d+))?"           # keep [l/h]N
    r"(?:([><])(\d+))?"             # threshold >N / <N
    r"((?:[+-]\d+)*)"               # modifiers +N/-N...
    r"$",
    re.IGNORECASE,
)


class DiceRoll:
    __slots__ = ("count", "sides", "keep", "keep_low", "threshold", "modifier")

    def __init__(self, count, sides, keep=None, keep_low=False, threshold=None, modifier=0):
        self.count = count
        self.sides = sides
        self.keep = keep
        self.keep_low = keep_low
        self.threshold = threshold
        self.modifier = modifier

    def roll(self):
        if self.sides == -1:
            return self._roll_fudge()
        raw = [random.randint(1, self.sides) for _ in range(self.count)]

        parts = []
        total = 0

        if self.keep is not None and self.keep < self.count:
            sorted_dice = sorted(raw, reverse=True)
            kept = sorted(raw, reverse=not self.keep_low)[:self.keep]
            kept_set = list(kept)
            remaining = list(raw)
            for v in kept_set:
                remaining.remove(v)
            for v in raw:
                if v in remaining:
                    parts.append(f"~~{v}~~")
                    remaining.remove(v)
                else:
                    parts.append(str(v))
            total = sum(kept) + self.modifier
        else:
            for v in raw:
                parts.append(str(v))
            total = sum(raw) + self.modifier

        total = max(total, 0) if self.sides != -1 else total

        desc = " + ".join(parts)
        if self.modifier:
            desc += f" + {self.modifier}" if self.modifier > 0 else f" - {abs(self.modifier)}"

        return raw, total, desc

    def _roll_fudge(self):
        values = [random.choice([-1, 0, 1]) for _ in range(self.count)]
        total = sum(values) + self.modifier
        symbols = ["−" if v == -1 else "0" if v == 0 else "+" for v in values]
        desc = " ".join(symbols)
        if self.modifier:
            desc += f" + {self.modifier}" if self.modifier > 0 else f" - {abs(self.modifier)}"
        return values, total, desc


def parse(expr: str):
    expr = expr.strip().lower()
    m = _DICE_RE.match(expr)
    if not m:
        raise ValueError(f"无法解析骰子表达式: {expr}")

    count = int(m.group(1)) if m.group(1) else 1
    sides_raw = m.group(2)
    keep_type = m.group(3)
    keep_count = m.group(4)
    th_op = m.group(5)
    th_val = m.group(6)
    mod_str = m.group(7)

    if count > 100:
        raise ValueError("骰子数量不能超过100")
    if count < 1:
        raise ValueError("骰子数量必须大于0")

    if sides_raw == "%":
        sides = 100
    elif sides_raw == "f":
        sides = -1
    else:
        sides = int(sides_raw)
        if sides > 10000:
            raise ValueError("骰子面数不能超过10000")
        if sides < 1:
            raise ValueError("骰子面数必须大于0")

    keep = int(keep_count) if keep_count else None
    keep_low = (keep_type == "l") if keep_type else False

    threshold = None
    if th_op and th_val is not None:
        threshold = (th_op, int(th_val))

    modifier = 0
    if mod_str:
        for p in re.findall(r"[+-]\d+", mod_str):
            modifier += int(p)

    return DiceRoll(count, sides, keep, keep_low, threshold, modifier)


def format_roll(count, sides, raw, total, desc, keep=None, threshold=None, modifier=0):
    label = f"{count}d{sides}"
    if keep:
        label += f"k{keep}"
    if modifier:
        label += f"{'+' if modifier > 0 else ''}{modifier}"
    return f"{label} = {desc} = {total}"
