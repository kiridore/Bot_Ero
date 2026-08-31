from core.base import CommandPlugin
from core.config import NICKNAME
from core.cq import text
from core.utils import register_plugin

@register_plugin
class CallPlugin(CommandPlugin):
    name = 'call_bot'
    description = '在被点名时回复机器人在线状态。'
    COMMANDS = (NICKNAME, "小埃同學")  # 简体走 NICKNAME，繁体别名保留字面量

    def handle(self):
        self.api.send_msg(text("我在~"))
