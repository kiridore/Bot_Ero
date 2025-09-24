from abc import abstractmethod
from core.database_manager import DbManager
from core.cq import *

class Plugin:
    commands = []
    desc = ""
    only_admin = False

    def __init__(self, context: dict, message_units: list):
        self.context = context  # 未解析raw数据
        self.dbmanager = DbManager()
        self.message_units = message_units

        self.time = context["time"]
        self.self_id = context["self_id"]
        self.post_type = context["post_type"]
        self.message_id = context["message_id"]
        self.message_type = context["message_type"]
        self.sub_type = context["sub_type"]
        self.sender = context["sender"]

        if self.message_type == "group":
            self.target_id = self.sender["group_id"]
        else:
            self.target_id = self.sender["user_id"]

    @abstractmethod
    def handle(self):
        pass
