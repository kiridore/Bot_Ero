# 指令解析管理调度模块
from core import logger
from core.base import Plugin
from core.cq import text
from core.message import MessageUnit
from plugins import *

class PlugManager:
    command_prefix = "/"
    def __init__(self) -> None:
        self.command_bind = {} # 运行时生成的动态指令绑定表
        self.message_units = []

        # 遍历所有的 Plugin 的子类，执行匹配
        for P in Plugin.__subclasses__():
            for command in P.commands:
                self.command_bind[command] = P

        self.time = 0
        self.self_id = 0
        self.post_type = ""
        self.message_id = 0
        self.message_type = ""
        self.sub_type = ""
        self.sender = {}
        self.target_id = 0

    def refresh(self, context: dict):
        self.message_units.clear()
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


    # 解析MessageEvent，根据内容触发对应对应功能
    def parse(self, context: dict):
        self.refresh(context)

        message_raw_list = context["message"]
        # 解析message数据
        for msg in message_raw_list:
            self.message_units.append(MessageUnit(msg))

        # 找到第一个text类型MessageUnit
        first_text_unit = None
        for unit in self.message_units:
            if unit.type == MessageUnit.MessageType.TEXT:
                first_text_unit = unit
                break
        # 找不到则直接退出, 节约性能
        if first_text_unit is None:
            return

        # 用空格作为分隔符，拆分text
        args = first_text_unit.text.split(" ")
        # 解析完成后删掉第一个unit
        if first_text_unit in self.message_units:
            self.message_units.remove(first_text_unit)

        # 判断第一个字符是否是command_prefix
        if args[0].startswith(self.command_prefix):
            command = args[0][len(self.command_prefix):] # 去掉前缀
            # 把剩下的内容作为参数，用于plugin初始化
            context["args"] = args[1:]
            if command in self.command_bind:
                plugin_class = self.command_bind[command]
                plugin = plugin_class(context, self.message_units)
                plugin.handle()
            else:
                # 输出找不到指令，并打印帮助
                from core.api_wrapper import send_msg
                send_msg(self.message_type, self.target_id, text("找不到指令: {}，使用 /菜单 查看支持功能喵~".format(command)))

plugin_manager_inst = PlugManager()
