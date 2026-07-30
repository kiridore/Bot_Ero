import random


_MAX_DICE = 100
_MAX_SIDES = 10000


def roll(count, sides):
    if count > _MAX_DICE:
        raise ValueError(f"骰子数量不能超过{_MAX_DICE}")
    if count < 1:
        raise ValueError("骰子数量必须大于0")
    if sides > _MAX_SIDES:
        raise ValueError(f"骰子面数不能超过{_MAX_SIDES}")
    if sides < 1:
        raise ValueError("骰子面数必须大于0")
    return [random.randint(1, sides) for _ in range(count)]


def _dice_detail(count, sides, values):
    s = " + ".join(str(v) for v in values)
    total = sum(values)
    label = f"{count}d{sides}"
    if count > 1:
        return total, f"[{label}={total}, {s}]"
    return total, f"[{label}={total}]"


def _eval_dice(count, sides, values):
    total, detail = _dice_detail(count, sides, values)
    return {"value": total, "detail": detail}


def _eval_advantage(sides):
    a = random.randint(1, sides)
    b = random.randint(1, sides)
    best = max(a, b)
    detail = f"{{{a} | {b} }}"
    return {"value": best, "detail": detail}


def _eval_disadvantage(sides):
    a = random.randint(1, sides)
    b = random.randint(1, sides)
    worst = min(a, b)
    detail = f"{{{a} | {b} }}"
    return {"value": worst, "detail": detail}


def parse(expr):
    if not expr:
        r = roll(1, 100)
        return r[0], f"[1d100={r[0]}]"

    tokens = _tokenize(expr)
    if not tokens:
        raise ValueError("无效表达式")

    # Multi-roll: N#expr
    if len(tokens) >= 3 and tokens[0][0] == "NUM" and tokens[1][0] == "#":
        count = tokens[0][1]
        if count < 1 or count > 10:
            raise ValueError("多轮掷骰次数应在1~10之间")
        results = []
        for _ in range(count):
            r, _ = _parse_add(list(tokens), 2)
            results.append(r)
        total = sum(r["value"] for r in results)
        detail = " ".join(r["detail"] for r in results)
        return total, detail

    result, _ = _parse_add(tokens, 0)
    return result["value"], result["detail"]


def _tokenize(s):
    tokens = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == " ":
            i += 1
            continue
        if c.isdigit():
            j = i
            while j < len(s) and s[j].isdigit():
                j += 1
            tokens.append(("NUM", int(s[i:j])))
            i = j
            continue
        if c in "+-*/()#%":
            tokens.append((c, c))
            i += 1
            continue
        if c == "*" and i + 1 < len(s) and s[i + 1] == "*":
            tokens.append(("**", "**"))
            i += 2
            continue
        if c in "dDbBpP":
            tokens.append((c.lower(), c))
            i += 1
            continue
        if s.startswith("优势", i):
            tokens.append(("优势", "优势"))
            i += 2
            continue
        if s.startswith("劣势", i):
            tokens.append(("劣势", "劣势"))
            i += 2
            continue
        break  # unknown char → reason text
    return tokens


def _parse_add(tokens, pos):
    left, pos = _parse_mul(tokens, pos)
    while pos < len(tokens):
        t = tokens[pos]
        if t[0] == "+":
            right, pos = _parse_mul(tokens, pos + 1)
            lv = left["value"]
            rv = right["value"]
            left = {"value": lv + rv, "detail": f"{left['detail']} + {right['detail']}"}
        elif t[0] == "-":
            right, pos = _parse_mul(tokens, pos + 1)
            lv = left["value"]
            rv = right["value"]
            left = {"value": lv - rv, "detail": f"{left['detail']} - {right['detail']}"}
        else:
            break
    return left, pos


def _parse_mul(tokens, pos):
    left, pos = _parse_unary(tokens, pos)
    while pos < len(tokens):
        t = tokens[pos]
        if t[0] == "*":
            right, pos = _parse_unary(tokens, pos + 1)
            lv = left["value"]
            rv = right["value"]
            left = {"value": lv * rv, "detail": f"({left['detail']}) * ({right['detail']})"}
        elif t[0] == "/":
            right, pos = _parse_unary(tokens, pos + 1)
            lv = left["value"]
            rv = right["value"]
            if rv == 0:
                raise ValueError("除数不能为0")
            left = {"value": lv // rv, "detail": f"({left['detail']}) / ({right['detail']})"}
        else:
            break
    return left, pos


def _parse_unary(tokens, pos):
    if pos >= len(tokens):
        raise ValueError("表达式不完整")
    t = tokens[pos]
    if t[0] == "+":
        return _parse_atom(tokens, pos + 1)
    if t[0] == "-":
        right, pos = _parse_atom(tokens, pos + 1)
        rv = right["value"]
        return {"value": -rv, "detail": f"-({right['detail']})"}, pos
    return _parse_atom(tokens, pos)


def _parse_atom(tokens, pos):
    if pos >= len(tokens):
        raise ValueError("表达式不完整")
    t = tokens[pos]

    # Number → check if followed by 'd' (NdN dice)
    if t[0] == "NUM":
        if pos + 1 < len(tokens) and tokens[pos + 1][0] == "d":
            return _parse_dice_explicit(tokens, pos)
        return {"value": t[1], "detail": str(t[1])}, pos + 1

    if t[0] == "(":
        result, pos = _parse_add(tokens, pos + 1)
        if pos >= len(tokens) or tokens[pos][0] != ")":
            raise ValueError("缺少 )")
        result["detail"] = f"({result['detail']})"
        return result, pos + 1

    if t[0] == "%":
        r = roll(1, 100)
        return {"value": r[0], "detail": f"[1d100={r[0]}]"}, pos + 1

    if t[0] == "d":
        return _parse_dice_implicit(tokens, pos)

    if t[0] == "b":
        return _parse_bonus(tokens, pos)

    if t[0] == "p":
        return _parse_penalty(tokens, pos)

    if t[0] == "优势":
        return _eval_advantage(20), pos + 1

    if t[0] == "劣势":
        return _eval_disadvantage(20), pos + 1

    raise ValueError(f"意外的标记: {t}")


def _parse_dice_explicit(tokens, pos):
    count = tokens[pos][1]
    pos += 2  # skip NUM and d
    sides, pos = _parse_sides(tokens, pos)
    return _parse_dice_result(count, sides, tokens, pos)


def _parse_dice_implicit(tokens, pos):
    pos += 1  # skip d
    sides, pos = _parse_sides(tokens, pos)
    return _parse_dice_result(1, sides, tokens, pos)


def _parse_sides(tokens, pos):
    if pos >= len(tokens):
        raise ValueError("骰子表达式需要面数")
    if tokens[pos][0] == "NUM":
        sides = tokens[pos][1]
        return sides, pos + 1
    if tokens[pos][0] == "%":
        return 100, pos + 1
    raise ValueError("骰子表达式需要面数")


def _parse_dice_result(count, sides, tokens, pos):
    # Check for advantage/disadvantage suffix
    if pos < len(tokens) and tokens[pos][0] == "优势":
        return _eval_advantage(sides), pos + 1
    if pos < len(tokens) and tokens[pos][0] == "劣势":
        return _eval_disadvantage(sides), pos + 1

    values = roll(count, sides)
    return _eval_dice(count, sides, values), pos


def _parse_bonus(tokens, pos):
    pos += 1  # skip b
    count = 1
    if pos < len(tokens) and tokens[pos][0] == "NUM":
        count = tokens[pos][1]
        if count < 1:
            raise ValueError("奖励骰数量必须大于0")
        pos += 1
    return _eval_bonus(count), pos


def _parse_penalty(tokens, pos):
    pos += 1  # skip p
    count = 1
    if pos < len(tokens) and tokens[pos][0] == "NUM":
        count = tokens[pos][1]
        if count < 1:
            raise ValueError("惩罚骰数量必须大于0")
        pos += 1
    return _eval_penalty(count), pos


def _eval_bonus(count):
    ten_dice = [random.randint(0, 9) for _ in range(count)]
    tens = [str(d) for d in ten_dice]
    base = random.randint(1, 100)
    all_tens = [base % 10] + ten_dice
    best = max(all_tens)
    result = (base // 10) * 10 + best
    if result > 100:
        result = 100
    detail = f"D100={base}, 奖励 {' '.join(tens)}"
    return {"value": result, "detail": detail}


def _eval_penalty(count):
    ten_dice = [random.randint(0, 9) for _ in range(count)]
    tens = [str(d) for d in ten_dice]
    base = random.randint(1, 100)
    all_tens = [base % 10] + ten_dice
    worst = min(all_tens)
    result = (base // 10) * 10 + worst
    if result > 100:
        result = 100
    detail = f"D100={base}, 惩罚 {' '.join(tens)}"
    return {"value": result, "detail": detail}
