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


def _strip_patterns_for_content(body: str) -> str:
    s = body
    rel_m = _REL_AFTER_RE.search(s)
    if _rel_match_valid(rel_m):
        s = s[: rel_m.start()] + " " + s[rel_m.end() :]
    else:
        abs_m = _ABS_DATE_RE.search(s)
        if abs_m:
            s = s[: abs_m.start()] + " " + s[abs_m.end() :]
    s = _TIME_RE.sub(" ", s)
    return " ".join(s.split())


def _parse_create_body(body: str) -> Union[Tuple[datetime, str], str]:
    m_time = _TIME_RE.search(body)
    has_time = m_time is not None
    rel_m = _REL_AFTER_RE.search(body)
    has_rel = _rel_match_valid(rel_m)
    abs_m = None if has_rel else _ABS_DATE_RE.search(body)
    has_abs = abs_m is not None
    if not has_rel and not has_abs and not has_time:
        return "请至少指定「…年后」相对日期、「…年…月…日」具体日期，或「HH:MM」时间。"
    content = _strip_patterns_for_content(body)
    if not content:
        return "请填写闹钟内容（不能为空）。"
    th, tm = 12, 0
    if has_time:
        th, tm = int(m_time.group(1)), int(m_time.group(2))
    now = datetime.now()
    fire: datetime
    if has_rel:
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
                fire = datetime(
                    yy, mm, dd, now.hour, now.minute, 0, 0
                )
        except ValueError:
            return "日期不合法，请检查年、月、日。"
    else:
        fire = datetime.combine(now.date(), dtime(th, tm, 0, 0))
    if fire <= now:
        return "闹钟触发时间不能早于或等于当前时刻（无日期时默认为当天该时刻）。"
    return fire, content


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
                "· 可同时写 HH:MM；无时间时，具体日用语义为当天当前时刻，相对日用语义为偏移后当前时刻。\n"
                "· /闹钟 HH:MM 内容 — 无日期时，为当天该时刻；若该时刻已过则无法设置。\n"
                "须至少包含上述日期之一或「HH:MM」，且必须有文字内容。\n"
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
        for rid, fat, c in rows:
            preview = c if len(c) <= 40 else c[:40] + "…"
            lines.append("#{} · {} · {}".format(rid, fat[:16], preview))
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
        fire, clean_content = parsed
        is_priv = self.bot_event.group_id is None
        aid = self.dbmanager.add_group_alarm(
            self.bot_event.user_id,
            fire,
            clean_content,
            self.bot_event.group_id,
            is_private=is_priv,
        )
        self.api.send_msg(
            text(
                "小埃记住了，已设置闹钟 #{}，将于 {} 提醒你喵：{}，我们到时候见~".format(
                    aid, fire.strftime("%Y-%m-%d %H:%M"), clean_content
                )
            )
        )

    def _handle_meta_due(self):
        db = self.dbmanager
        now = datetime.now()
        for row in db.get_due_alarms(now):
            aid, gid, creator_uid, content, fat, is_priv = (
                row[0],
                row[1],
                row[2],
                row[3],
                row[4],
                int(row[5] or 0),
            )
            if not db.try_mark_alarm_fired(aid):
                continue
            when_label = (fat or "")[:16]
            line = "你在「{}」吩咐小埃的事情，小埃来兑现了：\x20{}".format(when_label, content)
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
