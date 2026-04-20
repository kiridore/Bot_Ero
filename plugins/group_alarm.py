import calendar
import re
from datetime import datetime, timedelta, time as dtime
from typing import Optional, Tuple, Union

from core.base import Plugin
from core.cq import at, text
from core.utils import register_plugin

# 相对：…年后，缺省的年/月/日视为 0；须至少含一个数字
_REL_AFTER_RE = re.compile(r"(?:(\d+)年)?(?:(\d+)月)?(?:(\d+)日)?后")
# 绝对：不含「后」；按从长到短匹配，避免「1月」吞掉「1月15日」的一部分
_ABS_DATE_RE = re.compile(
    r"(?:\d+年\d+月\d+日|\d+年\d+月|\d+年\d+日|\d+年|\d+月\d+日|\d+月|\d+日)(?!后)"
)
_TIME_RE = re.compile(r"(?<![0-9])([0-1]?\d|2[0-3])[:：]([0-5]\d)(?![0-9])")

# 循环类型（与 DB recur_kind 一致）
RECUR_INTERVAL_DAYS = 1
RECUR_WEEKLY = 2
RECUR_YEARLY = 3
RECUR_MONTHLY = 4

# 前缀从长到短匹配；周一=1 … 周日=7（与 datetime.weekday 的 0=周一 对应：py = wd - 1）
_RECUR_MONTHLY_RE = re.compile(r"^每月(\d{1,2})[日号]")
_RECUR_YEARLY_RE = re.compile(r"^每年(\d{1,2})月(\d{1,2})[日号]")
_RECUR_WEEKLY_LONG_RE = re.compile(r"^每星期([一二三四五六日天])")
_RECUR_WEEKLY_RE = re.compile(r"^每周(周天|周日|[一二三四五六日天])")
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


def _weekday_token_to_n(token: str) -> Optional[int]:
    """返回 1–7（周一…周日）。token 为「一」「日」「周天」等。"""
    if not token:
        return None
    if token in ("周天", "周日"):
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
    md = re.search(r"(\d+)日", fragment)
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
            abs_m = _ABS_DATE_RE.search(s)
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
            return "循环前缀不能与「…日后」紧接在同一指令中。"
        am0 = _ABS_DATE_RE.match(rest_after)
        if am0:
            return "循环前缀不能与用于定时的具体日历日期紧接在同一指令中。"
        rel_m = None
        has_rel = False
        abs_m = None
        has_abs = False
    else:
        rel_m = _REL_AFTER_RE.search(body)
        has_rel = _rel_match_valid(rel_m)
        abs_m = None if has_rel else _ABS_DATE_RE.search(body)
        has_abs = abs_m is not None
    if not has_recur and not has_rel and not has_abs and not has_time:
        return (
            "请至少指定「每天/每日」「每N日/天」「每周…」「每年…月…日」「每月…日」之一，"
            "或「…年后」相对日期、「…年…月…日」具体日期，或「HH:MM」时间。"
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
        if has_time:
            fire = fire.replace(hour=th, minute=tm, second=0, microsecond=0)
    elif has_abs:
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
    return fire, content, recur


@register_plugin
class GroupAlarmPlugin(Plugin):
    name = "group_alarm"
    description = "群聊或私聊定时闹钟：/闹钟 …"
    _last_alarm_scan_minute = None

    def match(self, event_type):
        if event_type == "message":
            return self._match_text_command()
        if event_type == "meta":
            return self._should_scan_alarms()
        return False

    def _match_text_command(self):
        if not self.bot_event.message:
            return False
        m0 = self.bot_event.message[0]
        if m0.get("type") != "text":
            return False
        t = m0["data"]["text"].strip()
        return t.startswith("/闹钟") or t.startswith("/鬧鐘")

    def _should_scan_alarms(self):
        now = datetime.now()
        key = now.strftime("%Y-%m-%d %H:%M")
        if GroupAlarmPlugin._last_alarm_scan_minute == key:
            return False
        GroupAlarmPlugin._last_alarm_scan_minute = key
        return True

    def _command_body(self) -> Tuple[str, str]:
        raw = self.bot_event.message[0]["data"]["text"].strip()
        if raw.startswith("/鬧鐘"):
            return "/鬧鐘", raw[len("/鬧鐘") :].strip()
        return "/闹钟", raw[len("/闹钟") :].strip()

    def handle(self):
        if self.bot_event.post_type == "meta_event":
            self._handle_meta_due()
            return
        if not self.bot_event.message or self.bot_event.message[0].get("type") != "text":
            return
        _, body = self._command_body()
        if not body:
            self._send_usage()
            return
        first = body.split(None, 1)[0]
        if first == "一览" or first == "一覽":
            self._handle_list()
            return
        if first == "取消":
            rest = body[len(first) :].strip()
            self._handle_cancel(rest)
            return
        self._handle_create(body)

    def _send_usage(self):
        self.api.send_msg(
            text(
                "用法：\n"
                "· 「X年X月X日」无「后」— 具体日历日，可只写年/月/日或任意组合（缺省补当前年、月或 1 日）。\n"
                "· 「X年X月X日后」— 相对当前时刻的偏移；未写的年/月/日视为 0。\n"
                "· 循环（须写在开头，且不能与紧接的「…日后」或定时用具体日历日混用）：\n"
                "  「每天」「每日」— 等价于每 1 天；「每N日」或「每N天」— 每隔 N 天；"
                "「每周一」…「每周日」或「每星期一」…「每星期日」；\n"
                "  「每年M月D日」；「每月D日」。\n"
                "· 可同时写 HH:MM；无时间时，具体日/循环为当天当前时刻，相对「…日后」为偏移后当前时刻。\n"
                "· /闹钟 HH:MM 内容 — 无日期时，为当天该时刻；若该时刻已过则无法设置。\n"
                "须至少包含上述之一，且必须有文字内容。\n"
                "群聊与私聊均可设置；到点后在原会话中提醒。\n"
                "/闹钟 一览 — 查看本人待触发闹钟\n"
                "/闹钟 取消 <编号> — 取消对应闹钟（仅本人创建）"
            )
        )

    def _handle_list(self):
        gid = self.bot_event.group_id
        uid = self.bot_event.user_id
        rows = self.dbmanager.list_pending_alarms_for_user(uid, gid)
        if not rows:
            self.api.send_msg(text("你还没有待触发的闹钟。"))
            return
        lines = []
        for rid, fat, c, is_rec, rk, ra, rb, rc in rows:
            preview = c if len(c) <= 40 else c[:40] + "…"
            tnext = (fat or "")[:16]
            if int(is_rec or 0) and int(rk or 0) > 0:
                rec = _format_recur_desc(int(rk), int(ra or 0), int(rb or 0), int(rc or 0))
                lines.append("#{} · {} · {} · {}".format(rid, rec, tnext, preview))
            else:
                lines.append("#{} · {} · {}".format(rid, tnext, preview))
        self.api.send_msg(text("待触发闹钟：\n" + "\n".join(lines)))

    def _handle_cancel(self, rest: str):
        if not rest.isdigit():
            self.api.send_msg(text("请使用：/闹钟 取消 <编号>（编号见「一览」）。"))
            return
        aid = int(rest)
        ok = self.dbmanager.cancel_group_alarm(aid, self.bot_event.user_id, self.bot_event.group_id)
        if ok:
            self.api.send_msg(text("小埃已经取消闹钟 #{}。".format(aid)))
        else:
            self.api.send_msg(text("取消失败：编号不存在、已触发或不是你创建的闹钟。"))

    def _handle_create(self, body: str):
        parsed = _parse_create_body(body)
        if isinstance(parsed, str):
            self.api.send_msg(text(parsed))
            return
        fire, clean_content, recur = parsed
        is_priv = self.bot_event.group_id is None
        aid = self.dbmanager.add_group_alarm(
            self.bot_event.user_id,
            fire,
            clean_content,
            self.bot_event.group_id,
            is_private=is_priv,
            recur=recur,
        )
        if recur:
            k, a, b, c = recur
            extra = "（{} 循环）".format(_format_recur_desc(k, a, b, c))
        else:
            extra = ""
        self.api.send_msg(
            text(
                "小埃记住了，已设置闹钟 #{}，将于 {} 提醒你{}：「{}」".format(
                    aid, fire.strftime("%Y-%m-%d %H:%M"), extra, clean_content
                )
            )
        )

    def _handle_meta_due(self):
        db = self.dbmanager
        now = datetime.now()
        for row in db.get_due_alarms(now):
            aid = row[0]
            gid = row[1]
            creator_uid = row[2]
            content = row[3]
            fat = row[4]
            is_priv = int(row[5] or 0)
            is_rec = int(row[6] or 0)
            rk = int(row[7] or 0)
            ra = int(row[8] or 0)
            rb = int(row[9] or 0)
            rc = int(row[10] or 0)
            when_label = (fat or "")[:16]
            line = "预约「{}」的小埃提醒服务来了喵：\x20{}".format(when_label, content)
            if is_rec and rk > 0:
                if is_priv:
                    self.api.call_api(
                        "send_private_msg",
                        {"user_id": int(creator_uid), "message": (text(line),)},
                    )
                else:
                    self.api.call_api(
                        "send_group_msg",
                        {
                            "group_id": int(gid),
                            "message": (at(int(creator_uid)), text("\n"), text(line)),
                        },
                    )
                prev_dt = datetime.strptime(fat, "%Y-%m-%d %H:%M:%S")
                nxt = _next_recurring_fire(prev_dt, now, rk, ra, rb, rc)
                db.try_advance_recurring_fire_at(aid, fat, nxt)
            else:
                if not db.try_mark_alarm_fired(aid):
                    continue
                if is_priv:
                    self.api.call_api(
                        "send_private_msg",
                        {"user_id": int(creator_uid), "message": (text(line),)},
                    )
                else:
                    self.api.call_api(
                        "send_group_msg",
                        {
                            "group_id": int(gid),
                            "message": (at(int(creator_uid)), text("\n"), text(line)),
                        },
                    )
