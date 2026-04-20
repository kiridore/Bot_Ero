import calendar
import re
from datetime import datetime, timedelta, time as dtime
from typing import Tuple, Union

from core.base import Plugin
from core.cq import at, text
from core.utils import register_plugin

_YMD_RE = re.compile(r"(\d+)年(\d+)月(\d+)日")
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


def _strip_patterns_for_content(s: str) -> str:
    s = _YMD_RE.sub(" ", s)
    s = _TIME_RE.sub(" ", s)
    return " ".join(s.split())


def _parse_create_body(body: str) -> Union[Tuple[datetime, str], str]:
    m_ymd = _YMD_RE.search(body)
    m_time = _TIME_RE.search(body)
    has_ymd = m_ymd is not None
    has_time = m_time is not None
    if not has_ymd and not has_time:
        return "请至少指定「a年b月c日」相对日期，或「HH:MM」时间。"
    content = _strip_patterns_for_content(body)
    if not content:
        return "请填写闹钟内容（不能为空）。"
    ya = ma = da = 0
    if has_ymd:
        ya, ma, da = int(m_ymd.group(1)), int(m_ymd.group(2)), int(m_ymd.group(3))
    th, tm = 12, 0
    if has_time:
        th, tm = int(m_time.group(1)), int(m_time.group(2))
    now = datetime.now()
    if has_ymd and has_time:
        base = _apply_year_month_day_offset(now, ya, ma, da)
        fire = base.replace(hour=th, minute=tm, second=0, microsecond=0)
    elif has_ymd and not has_time:
        fire = _apply_year_month_day_offset(now, ya, ma, da)
    else:
        tomorrow = now.date() + timedelta(days=1)
        fire = datetime.combine(tomorrow, dtime(th, tm, 0, 0))
    if fire <= now:
        return "闹钟触发时间不能早于或等于当前时间。"
    return fire, content


@register_plugin
class GroupAlarmPlugin(Plugin):
    name = "group_alarm"
    description = "群内定时闹钟：/闹钟 …"
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
        if self.bot_event.group_id is None:
            self.api.send_msg(text("请在群内设置闹钟，以便到点 @ 你提醒。"))
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
                "· /闹钟 a年b月c日 HH:MM 内容 — 相对当前 a年b月c日后的指定时刻\n"
                "· /闹钟 a年b月c日 内容 — 仅有相对日期时，触发时刻与当前时刻相同（秒归零）\n"
                "· /闹钟 HH:MM 内容 — 无日期时，视为明天该时刻\n"
                "须至少包含「a年b月c日」或「HH:MM」之一，且必须有文字内容。\n"
                "/闹钟 一览 — 查看本人待触发闹钟\n"
                "/闹钟 取消 <编号> — 取消对应闹钟（仅本人创建）"
            )
        )

    def _handle_list(self):
        gid = self.bot_event.group_id
        uid = self.bot_event.user_id
        rows = self.dbmanager.list_pending_alarms_for_user(gid, uid)
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
        ok = self.dbmanager.cancel_group_alarm(
            aid, self.bot_event.group_id, self.bot_event.user_id
        )
        if ok:
            self.api.send_msg(text("已取消闹钟 #{}。".format(aid)))
        else:
            self.api.send_msg(text("取消失败：编号不存在、已触发或不是你创建的闹钟。"))

    def _handle_create(self, body: str):
        parsed = _parse_create_body(body)
        if isinstance(parsed, str):
            self.api.send_msg(text(parsed))
            return
        fire, clean_content = parsed
        aid = self.dbmanager.add_group_alarm(
            self.bot_event.group_id, self.bot_event.user_id, fire, clean_content
        )
        self.api.send_msg(
            text(
                "已设置闹钟 #{}，将于 {} 在本群 @ 你：{}".format(
                    aid, fire.strftime("%Y-%m-%d %H:%M"), clean_content
                )
            )
        )

    def _handle_meta_due(self):
        db = self.dbmanager
        now = datetime.now()
        for row in db.get_due_alarms(now):
            aid, gid, creator_uid, content = row[0], row[1], row[2], row[3]
            if not db.try_mark_alarm_fired(aid):
                continue
            self.api.call_api(
                "send_group_msg",
                {
                    "group_id": int(gid),
                    "message": (at(int(creator_uid)), text("\n闹钟："), text(content)),
                },
            )
