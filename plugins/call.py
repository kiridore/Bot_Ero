from core.base import Plugin
from core.cq import text

class CallPlugin(Plugin):
    def match(self, message_type):
        return self.on_full_match("小埃同学")

    def handle(self):
        self.api.send_msg(text("我在~"))
