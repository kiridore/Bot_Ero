from core.cq import *
from core.api import ApiWrapper
from core.database_manager import DbManager

only_to_me_flag = False

NICKNAME = "小埃同学"         # 机器人昵称
SUPER_USER = [1057613133]   # 主人的 QQ 号
BOT_QQ = "3915014383"


class Plugin:
    def __init__(self, context: dict):
        self.context = context
        self.api = ApiWrapper(context)
        self.dbmanager = DbManager()

    def match(self, event_type = "message") -> bool:
        return False

    def handle(self):
        pass

    def on_message(self) -> bool:
        if self.context.get("post_type" , "") == "":
            return False
        return self.context["post_type"] == "message"

    def on_full_match(self, keyword="") -> bool:
        if self.context.get("message", "") == "":
            return False
        message_list = self.context["message"]
        if len(message_list) == 1:
            msg = message_list[0]
            return msg['type'] == 'text' and msg['data']['text'] == keyword
        return False

    def on_begin_with(self, keyword="") -> bool:
        if self.context.get( "message" , "") == "":
            return False

        msg = self.context["message"][0]
        if (msg["type"] == 'text'):
            return msg['type'] == 'text' and msg['data']['text'] == keyword
        return False

    def on_command(self, command) -> bool:
        if self.context.get( "message" , "") == "":
            return False

        msg = self.context["message"][0]
        if (msg["type"] == 'text'):
            sp = msg["data"]["text"].split(" ")
            if sp[0] == command:
                raw_data = self.context["message"][0]
                if raw_data['type'] != 'text':
                    return False
                msg = raw_data['data']['text']
                self.args = msg.split(" ")
                return True
            else:
                return False
        return False

    def super_user(self) -> bool:
        if self.context.get("user_id" , "") == "":
            return False
        return self.context["user_id"] in SUPER_USER

    def admin_user(self) -> bool:
        if self.context.get("sender" , "") == "":
            return False

        return self.super_user() or self.context["sender"]["role"] in ("admin", "owner")
