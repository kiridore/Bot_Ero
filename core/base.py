from core.cq import *
from core.api import ApiWrapper
from core.database_manager import DbManager
from datetime import datetime
from typing import Iterable, Optional, Set, Tuple, Union

from core.event import Event

only_to_me_flag = False

NICKNAME = "小埃同学"         # 机器人昵称
SUPER_USER = [1057613133]   # 主人的 QQ 号
BOT_QQ = "3915014383"


class Plugin:
    name = ""
    description = ""

    def __init__(self, raw_context: dict):
        self.bot_event = Event(raw_context)
        self.api = ApiWrapper(raw_context)
        self.dbmanager = DbManager()

    def match(self, event_type = "message") -> bool:
        return False

    def handle(self):
        pass

    def on_message(self) -> bool:
        if self.bot_event.post_type == None:
            return False
        return self.bot_event.post_type == "message"

    def on_full_match(self, keyword="") -> bool:
        if self.bot_event.message == None:
            return False
        message_list = self.bot_event.message
        if len(message_list) == 1:
            msg = message_list[0]
            if msg['type'] != 'text': return False

            msg_text:str = msg['data']['text'] 
            return msg_text.strip() == keyword
        return False

    def on_full_match_any(self, *keywords) -> bool:
        if self.bot_event.message == None:
            return False
        message_list = self.bot_event.message
        if len(message_list) != 1:
            return False
        msg = message_list[0]
        if msg["type"] != "text":
            return False
        msg_text = msg["data"]["text"].strip()
        return msg_text in keywords

    def on_begin_with(self, keyword="") -> bool:
        if self.bot_event.message == []:
            return False

        msg = self.bot_event.message[0]
        if (msg["type"] == 'text'):
            return msg['type'] == 'text' and msg['data']['text'].strip() == keyword
        return False

    def on_command(self, command) -> bool:
        if self.bot_event.message == []:
            return False

        msg = self.bot_event.message[0]
        if (msg["type"] == 'text'):
            sp = msg["data"]["text"].split(" ")
            if sp[0] == command:
                raw_data = self.bot_event.message[0]
                if raw_data['type'] != 'text':
                    return False
                msg = raw_data['data']['text']
                self.args = msg.split(" ")
                return True
            else:
                return False
        return False

    def on_command_any(self, *commands) -> bool:
        if self.bot_event.message == []:
            return False
        raw_data = self.bot_event.message[0]
        if raw_data["type"] != "text":
            return False
        text_body = raw_data["data"]["text"]
        sp = text_body.split(" ")
        if sp[0] in commands:
            self.args = text_body.split(" ")
            return True
        return False

    def super_user(self) -> bool:
        if self.bot_event.user_id == None:
            return False
        return self.bot_event.user_id in SUPER_USER

    def admin_user(self) -> bool:
        if self.bot_event.sender == None:
            return False

        return self.super_user() or self.bot_event.sender.get("role", "") in ("admin", "owner")


AnnualDateItem = Union[Tuple[int, int], str]


class TimedHeartbeatPlugin(Plugin):
    # 触发时间，格式 HH:MM（24小时制）
    RUN_AT = "00:00"
    # 可选：仅在指定星期运行。使用 ISO 星期：1=周一 … 7=周日。None 或空序列表示不限制。
    RUN_WEEKDAYS: Optional[Iterable[int]] = None
    # 可选：仅在每年指定月日运行。元素可为 (month, day) 或 "MM-DD" / "M-D" 字符串。None 或空序列表示不限制。
    # 若与 RUN_WEEKDAYS 同时配置，则两者都满足时才触发（AND）。
    RUN_ANNUAL_DATES: Optional[Iterable[AnnualDateItem]] = None
    _last_run_minute = {}

    @staticmethod
    def _annual_dates_as_set(raw: Iterable[AnnualDateItem]) -> Set[Tuple[int, int]]:
        out: Set[Tuple[int, int]] = set()
        for item in raw:
            if isinstance(item, str):
                s = item.strip().replace("/", "-")
                parts = s.split("-")
                if len(parts) != 2:
                    continue
                out.add((int(parts[0]), int(parts[1])))
            elif isinstance(item, (tuple, list)) and len(item) == 2:
                out.add((int(item[0]), int(item[1])))
        return out

    def _passes_weekday_filter(self, now: datetime) -> bool:
        cls = type(self)
        days = getattr(cls, "RUN_WEEKDAYS", None)
        if not days:
            return True
        return now.isoweekday() in set(days)

    def _passes_annual_filter(self, now: datetime) -> bool:
        cls = type(self)
        dates = getattr(cls, "RUN_ANNUAL_DATES", None)
        if not dates:
            return True
        allowed = self._annual_dates_as_set(dates)
        return (now.month, now.day) in allowed

    def should_run_on_heartbeat(self, event_type: str) -> bool:
        if event_type != "meta":
            return False

        now = datetime.now()
        current_minute = now.strftime("%H:%M")
        if current_minute != self.RUN_AT:
            return False

        if not self._passes_weekday_filter(now):
            return False
        if not self._passes_annual_filter(now):
            return False

        run_key = now.strftime("%Y-%m-%d %H:%M")
        plugin_name = type(self).__name__
        if self._last_run_minute.get(plugin_name) == run_key:
            return False

        self._last_run_minute[plugin_name] = run_key
        return True

    def match(self, event_type="message") -> bool:
        return self.should_run_on_heartbeat(event_type)
