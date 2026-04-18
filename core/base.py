from core.cq import *
from core.api import ApiWrapper
from core.database_manager import DbManager
from datetime import datetime

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

    def on_begin_with(self, keyword="") -> bool:
        if self.bot_event.message == None:
            return False

        msg = self.bot_event.message[0]
        if (msg["type"] == 'text'):
            return msg['type'] == 'text' and msg['data']['text'].strip() == keyword
        return False

    def on_command(self, command) -> bool:
        if self.bot_event.message == None:
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

    def super_user(self) -> bool:
        if self.bot_event.user_id == None:
            return False
        return self.bot_event.user_id in SUPER_USER

    def admin_user(self) -> bool:
        if self.bot_event.sender == None:
            return False

        return self.super_user() or self.bot_event.sender["role"] in ("admin", "owner")


class TimedHeartbeatPlugin(Plugin):
    # 触发时间，格式 HH:MM（24小时制）
    RUN_AT = "00:00"
    _last_run_minute = {}

    def should_run_on_heartbeat(self, event_type: str) -> bool:
        if event_type != "meta":
            return False

        now = datetime.now()
        current_minute = now.strftime("%H:%M")
        if current_minute != self.RUN_AT:
            return False

        run_key = now.strftime("%Y-%m-%d %H:%M")
        plugin_name = type(self).__name__
        if self._last_run_minute.get(plugin_name) == run_key:
            return False

        self._last_run_minute[plugin_name] = run_key
        return True

    def match(self, event_type="message") -> bool:
        return self.should_run_on_heartbeat(event_type)
