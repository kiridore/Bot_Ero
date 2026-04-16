from core.base import Plugin
from core.cq import text
from core.utils import register_plugin

@register_plugin
class CallPlugin(Plugin):
    name = 'call_bot'
    description = '在被点名时回复机器人在线状态。'

    def match(self, message_type):
        return self.on_full_match("小埃同学")

    def handle(self):
        self.api.send_msg(text("我在~"))
