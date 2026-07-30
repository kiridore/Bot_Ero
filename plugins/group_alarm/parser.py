import calendar
import re
from datetime import datetime, timedelta, time as dtime
from typing import Optional, Tuple, Union

# 相对：…年…月…日…(时|時|小时|小時)…(分|分钟|分鐘)後|后（均可省略，视为 0）；长词序在前；须至少含一个数字
_REL_AFTER_RE = re.compile(
    r"(?:(\d+)年)?(?:(\d+)月)?(?:(\d+)(?:日|天))?"
    r"(?:(\d+)(?:小時|小时|時|时))?(?:(\d+)(?:分鐘|分钟|分))?(?:後|后)"
)
# 最短提前量：须至少满 5 分钟（拒绝 fire - now < 5 分钟；刚好 5 分钟允许）
_MIN_ALARM_LEAD = timedelta(minutes=5)
# 绝对：不含「后/後」；日可写作 日/號/号；按从长到短匹配
_ABS_DAY = r"(?:日|號|号)"
_ABS_DATE_RE = re.compile(
    rf"(?:\d+年\d+月\d+{_ABS_DAY}|\d+年\d+月|\d+年\d+{_ABS_DAY}|\d+年|\d+月\d+{_ABS_DAY}|\d+月|\d+{_ABS_DAY})(?!后|後)"
)
# 与 YYYY年MM月DD日 等价的公历 YYYY-MM-DD（月日允许 1～2 位，解析后再校验）
_ISO_DATE_RE = re.compile(
    r"(?<![0-9])(?P<y>[12][0-9]{3})-(?P<mo>\d{1,2})-(?P<d>\d{1,2})(?![0-9])"
)
_TIME_RE = re.compile(r"(?<![0-9])([0-1]?\d|2[0-3])[:：]([0-5]\d)(?![0-9])")


def _find_first_absolute_date(s: str) -> Optional[re.Match]:
    """在全文取最先出现的公历「中文片段」或「YYYY-MM-DD」。"""
    cands = []
    m1 = _ISO_DATE_RE.search(s)
    m2 = _ABS_DATE_RE.search(s)
    if m1:
        cands.append(m1)
    if m2:
        cands.append(m2)
    if not cands:
        return None
    return min(cands, key=lambda m: m.start())


def _abs_at_line_start(rest: str) -> Optional[re.Match]:
    """与循环前缀互斥时：判断 rest 是否以公历绝对日期（中文或 ISO）开头。"""
    t = rest.strip()
    m = _ISO_DATE_RE.match(t)
    if m:
        return m
    return _ABS_DATE_RE.match(t)

# 循环类型（与 DB recur_kind 一致）
RECUR_INTERVAL_DAYS = 1
RECUR_WEEKLY = 2
RECUR_YEARLY = 3
RECUR_MONTHLY = 4

# 前缀从长到短匹配；周一=1 … 周日=7（与 datetime.weekday 的 0=周一 对应：py = wd - 1）
_RECUR_MONTHLY_RE = re.compile(rf"^每月(\d{{1,2}}){_ABS_DAY}")
_RECUR_YEARLY_RE = re.compile(rf"^每年(\d{{1,2}})月(\d{{1,2}}){_ABS_DAY}")
_RECUR_WEEKLY_LONG_RE = re.compile(r"^每星期([一二三四五六日天])")
_RECUR_WEEKLY_RE = re.compile(r"^每(?:周|週)(周天|周日|週日|[一二三四五六日天])")
# 「每天」「每日」中间无数字，等价于每 1 天（须在「每N日/天」之前尝试，避免与「每3日」冲突）
_RECUR_EVERY_DAY_RE = re.compile(r"^每(?:日|天)")
_RECUR_N_DAYS_RE = re.compile(r"^每(\d+)(?:日|天)")


def _apply_year_month_day_offset(dt: datetime, years: int, months: int, days: int) -> datetime:
    y = dt.year + int(years)
    m = dt.month + int(months)
    d = dt.day
    while m > 12:
        y += 1
        m -= 12
    while m < 1:
        y -= 1
        m += 12
    last = calendar.monthrange(y, m)[1]
    d = min(d, last)
    out = dt.replace(year=y, month=m, day=d, second=0, microsecond=0)
    return out + timedelta(days=int(days))


def _rel_match_valid(m: re.Match) -> bool:
    if not m:
        return False
    span = m.group(0)
    return bool(re.search(r"\d", span[:-1]))


def _rel_has_embedded_clock(m: re.Match) -> bool:
    """相对片段内是否写了「X时/…小时」或「Y分/…分钟」（与独立 HH:MM 区分）。"""
    g = m.groups()
    if len(g) < 5:
        return False
    return g[3] is not None or g[4] is not None


def _rel_embedded_hours_minutes(m: re.Match) -> Tuple[int, int]:
    g = m.groups()
    ha = int(g[3]) if len(g) > 3 and g[3] is not None else 0
    mia = int(g[4]) if len(g) > 4 and g[4] is not None else 0
    return ha, mia


def _weekday_token_to_n(token: str) -> Optional[int]:
    """返回 1–7（周一…周日）。token 为「一」「日」「周天」等。"""
    if not token:
        return None
    if token in ("周天", "周日", "週日"):
        return 7
    if len(token) != 1:
        return None
    mp = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}
    return mp.get(token)


def _format_recur_desc(kind: int, a: int, b: int, _c: int) -> str:
    if kind == RECUR_INTERVAL_DAYS:
        if int(a) == 1:
            return "每天"
        return "每{}日".format(int(a))
    if kind == RECUR_WEEKLY:
        cn = ("一", "二", "三", "四", "五", "六", "日")
        return "每周{}".format(cn[int(a) - 1])
    if kind == RECUR_YEARLY:
        return "每年{}月{}日".format(int(a), int(b))
    if kind == RECUR_MONTHLY:
        return "每月{}日".format(int(a))
    return "循环"


def _try_match_recurring(s0: str) -> Optional[Union[str, Tuple[int, int, int, int, re.Match]]]:
    """
    若 s0 以支持的循环前缀开头，返回 (recur_kind, a, b, c, match)；
    若语法不合法返回错误字符串。
    """
    m = _RECUR_MONTHLY_RE.match(s0)
    if m:
        dom = int(m.group(1))
        if dom < 1 or dom > 31:
            return "「每月」后面的日须在 1–31 之间。"
        return (RECUR_MONTHLY, dom, 0, 0, m)
    m = _RECUR_YEARLY_RE.match(s0)
    if m:
        mo, d_ = int(m.group(1)), int(m.group(2))
        if mo < 1 or mo > 12:
            return "「每年」月须在 1–12 之间。"
        if d_ < 1 or d_ > 31:
            return "「每年」日须在 1–31 之间。"
        return (RECUR_YEARLY, mo, d_, 0, m)
    m = _RECUR_WEEKLY_LONG_RE.match(s0)
    if not m:
        m = _RECUR_WEEKLY_RE.match(s0)
    if m:
        tok = m.group(1)
        wd = _weekday_token_to_n(tok)
        if wd is None:
            return "「每周 / 每星期」后请跟周一至周日（如：每周三、每星期日）。"
        return (RECUR_WEEKLY, wd, 0, 0, m)
    m = _RECUR_EVERY_DAY_RE.match(s0)
    if m:
        return (RECUR_INTERVAL_DAYS, 1, 0, 0, m)
    m = _RECUR_N_DAYS_RE.match(s0)
    if m:
        n = int(m.group(1))
        if n < 1:
            return "「每N日/天」的 N 须至少为 1。"
        return (RECUR_INTERVAL_DAYS, n, 0, 0, m)
    return None


def _extract_ymd_from_fragment(fragment: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """从「…年…月…日」片段解析整数，未出现的部分为 None。"""
    y = m_ = d = None
    my = re.search(r"(\d+)年", fragment)
    if my:
        y = int(my.group(1))
    mm = re.search(r"(\d+)月", fragment)
    if mm:
        m_ = int(mm.group(1))
    md = re.search(r"(\d+)(?:日|號|号)", fragment)
    if md:
        d = int(md.group(1))
    return y, m_, d


def _build_absolute_ymd(
    now: datetime, gy: Optional[int], gm: Optional[int], gd: Optional[int]
) -> Tuple[int, int, int]:
    """不完整绝对日期：缺省补当前年/月或 1 月 1 日等。"""
    y0, m0, d0 = now.year, now.month, now.day
    if gy is not None and gm is not None and gd is not None:
        y, m_, d = gy, gm, gd
    elif gy is not None and gm is not None:
        y, m_, d = gy, gm, 1
    elif gy is not None and gd is not None:
        y, m_, d = gy, m0, gd
    elif gy is not None:
        y, m_, d = gy, 1, 1
    elif gm is not None and gd is not None:
        y, m_, d = y0, gm, gd
    elif gm is not None:
        y, m_, d = y0, gm, 1
    elif gd is not None:
        y, m_, d = y0, m0, gd
    else:
        raise ValueError("empty ymd")
    if m_ < 1 or m_ > 12:
        raise ValueError("bad month")
    last = calendar.monthrange(y, m_)[1]
    d = max(1, min(int(d), last))
    return y, m_, d


def _now_trunc(now: datetime) -> datetime:
    return now.replace(second=0, microsecond=0)


def _first_fire_interval_days(
    now: datetime, n: int, has_time: bool, th: int, tm: int
) -> datetime:
    base = _now_trunc(now)
    fire = base + timedelta(days=n)
    if has_time:
        fire = fire.replace(hour=th, minute=tm, second=0, microsecond=0)
    guard = 0
    while fire <= _now_trunc(now) and guard < 10000:
        fire = fire + timedelta(days=n)
        if has_time:
            fire = fire.replace(hour=th, minute=tm, second=0, microsecond=0)
        guard += 1
    return fire


def _first_fire_weekly(now: datetime, user_wd: int, has_time: bool, th: int, tm: int) -> datetime:
    target_py = int(user_wd) - 1
    h = th if has_time else now.hour
    mi = tm if has_time else now.minute
    delta = (target_py - now.weekday()) % 7
    d0 = now.date() + timedelta(days=delta)
    fire = datetime(d0.year, d0.month, d0.day, h, mi, 0, 0)
    if fire <= _now_trunc(now):
        fire = fire + timedelta(days=7)
    return fire


def _first_fire_monthly(
    now: datetime, dom: int, has_time: bool, th: int, tm: int
) -> Union[datetime, str]:
    h = th if has_time else now.hour
    mi = tm if has_time else now.minute
    y, m = now.year, now.month
    last = calendar.monthrange(y, m)[1]
    d = min(dom, last)
    try:
        fire = datetime(y, m, d, h, mi, 0, 0)
    except ValueError:
        return "「每月」对应的日期在本月无效。"
    if fire <= _now_trunc(now):
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
        last = calendar.monthrange(y, m)[1]
        d = min(dom, last)
        try:
            fire = datetime(y, m, d, h, mi, 0, 0)
        except ValueError:
            return "「每月」对应的日期在下一月无效。"
    return fire


def _first_fire_yearly(
    now: datetime, month: int, day: int, has_time: bool, th: int, tm: int
) -> Union[datetime, str]:
    h = th if has_time else now.hour
    mi = tm if has_time else now.minute
    y = now.year
    last = calendar.monthrange(y, month)[1]
    d = min(day, last)
    try:
        fire = datetime(y, month, d, h, mi, 0, 0)
    except ValueError:
        return "「每年」月日组合无效。"
    if fire <= _now_trunc(now):
        y += 1
        last = calendar.monthrange(y, month)[1]
        d = min(day, last)
        try:
            fire = datetime(y, month, d, h, mi, 0, 0)
        except ValueError:
            return "「每年」在下一年的该月日无效。"
    return fire


def _next_recurring_fire(prev: datetime, now: datetime, kind: int, a: int, b: int, _c: int) -> datetime:
    if kind == RECUR_INTERVAL_DAYS:
        n = int(a)
        nxt = prev + timedelta(days=n)
        g = 0
        while nxt <= _now_trunc(now) and g < 10000:
            nxt = nxt + timedelta(days=n)
            g += 1
        return nxt
    if kind == RECUR_WEEKLY:
        return prev + timedelta(days=7)
    if kind == RECUR_MONTHLY:
        dom = int(a)
        y, m = prev.year, prev.month
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
        last = calendar.monthrange(y, m)[1]
        d = min(dom, last)
        return prev.replace(year=y, month=m, day=d, second=0, microsecond=0)
    if kind == RECUR_YEARLY:
        mo, dy = int(a), int(b)
        y = prev.year + 1
        last = calendar.monthrange(y, mo)[1]
        d = min(dy, last)
        return prev.replace(year=y, month=mo, day=d, second=0, microsecond=0)
    return prev + timedelta(days=1)


def _strip_patterns_for_content(body: str) -> str:
    s = body.strip()
    r = _try_match_recurring(s)
    if isinstance(r, tuple):
        s = s[r[4].end() :].strip()
    else:
        rel_m = _REL_AFTER_RE.search(s)
        if _rel_match_valid(rel_m):
            s = s[: rel_m.start()] + " " + s[rel_m.end() :]
        else:
            abs_m = _find_first_absolute_date(s)
            if abs_m:
                s = s[: abs_m.start()] + " " + s[abs_m.end() :]
    s = _TIME_RE.sub(" ", s)
    return " ".join(s.split())


def _parse_create_body(body: str) -> Union[Tuple[datetime, str, Optional[Tuple[int, int, int, int]]], str]:
    s0 = body.strip()
    recur_info = _try_match_recurring(s0)
    has_recur = isinstance(recur_info, tuple)
    recur_err: Optional[str] = recur_info if isinstance(recur_info, str) else None
    if recur_err:
        return recur_err
    m_time = _TIME_RE.search(body)
    has_time = m_time is not None
    if has_recur:
        _k, _a, _b, _c, em = recur_info
        rest_after = s0[em.end() :].strip()
        rm0 = _REL_AFTER_RE.match(rest_after)
        if _rel_match_valid(rm0):
            return "循环前缀不能与「…日后／…日後」紧接在同一指令中。"
        am0 = _abs_at_line_start(rest_after)
        if am0:
            return "循环前缀不能与用于定时的具体日历日期紧接在同一指令中。"
        rel_m = None
        has_rel = False
        abs_m = None
        has_abs = False
    else:
        rel_m = _REL_AFTER_RE.search(body)
        has_rel = _rel_match_valid(rel_m)
        abs_m = None if has_rel else _find_first_absolute_date(body)
        has_abs = abs_m is not None
    if not has_recur and not has_rel and not has_abs and not has_time:
        return (
            "请至少指定「每天/每日」「每N日/天」「每周…」「每年…月…日」「每月…日」之一，"
            "或「…年…月…日…(时|小时)…(分|分钟)后」相对时间、"
            "「…年…月…日」或 YYYY-MM-DD 具体日期，或「HH:MM」时间。"
        )
    content = _strip_patterns_for_content(body)
    if not content:
        return "请填写闹钟内容（不能为空）。"
    th, tm = 12, 0
    if has_time:
        th, tm = int(m_time.group(1)), int(m_time.group(2))
    now = datetime.now()
    fire: datetime
    recur: Optional[Tuple[int, int, int, int]] = None
    if has_recur:
        kind, ra, rb, rc, _em = recur_info
        if kind == RECUR_INTERVAL_DAYS:
            fire = _first_fire_interval_days(now, ra, has_time, th, tm)
        elif kind == RECUR_WEEKLY:
            fire = _first_fire_weekly(now, ra, has_time, th, tm)
        elif kind == RECUR_MONTHLY:
            fr = _first_fire_monthly(now, ra, has_time, th, tm)
            if isinstance(fr, str):
                return fr
            fire = fr
        elif kind == RECUR_YEARLY:
            fr = _first_fire_yearly(now, ra, rb, has_time, th, tm)
            if isinstance(fr, str):
                return fr
            fire = fr
        else:
            return "不支持的循环类型。"
        recur = (kind, ra, rb, rc)
    elif has_rel:
        ya = int(rel_m.group(1) or 0)
        ma = int(rel_m.group(2) or 0)
        da = int(rel_m.group(3) or 0)
        fire = _apply_year_month_day_offset(now, ya, ma, da)
        if _rel_has_embedded_clock(rel_m):
            ha, mia = _rel_embedded_hours_minutes(rel_m)
            fire = fire + timedelta(hours=ha, minutes=mia)
        elif has_time:
            fire = fire.replace(hour=th, minute=tm, second=0, microsecond=0)
    elif has_abs:
        if "y" in abs_m.groupdict():
            try:
                yy = int(abs_m.group("y"))
                mm = int(abs_m.group("mo"))
                dd = int(abs_m.group("d"))
            except (TypeError, ValueError):
                return "日期不合法，请检查 YYYY-MM-DD 格式。"
        else:
            gy, gm, gd = _extract_ymd_from_fragment(abs_m.group(0))
            try:
                yy, mm, dd = _build_absolute_ymd(now, gy, gm, gd)
            except ValueError:
                return "日期不合法，请检查年、月、日。"
        if yy < datetime.min.year or yy > 9999:
            return "年份超出可表示范围。"
        try:
            if has_time:
                fire = datetime(yy, mm, dd, th, tm, 0, 0)
            else:
                fire = datetime(yy, mm, dd, now.hour, now.minute, 0, 0)
        except ValueError:
            return "日期不合法，请检查年、月、日。"
    else:
        fire = datetime.combine(now.date(), dtime(th, tm, 0, 0))
    if fire <= now:
        return "闹钟触发时间不能早于或等于当前时刻（无日期时默认为当天该时刻）。"
    if fire - now < _MIN_ALARM_LEAD:
        return "闹钟须设置在至少 5 分钟之后（距当前时刻不足 5 分钟）。"
    return fire, content, recur