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

    @abstractmethod
    def handle(self):
        pass
