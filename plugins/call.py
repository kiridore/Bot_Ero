from core.base import Plugin
from core.cq import text

class MenuPlugin(Plugin):
    def match(self):
        return self.on_full_match("小埃同学") or self.only_to_me()

    def handle(self):
        self.send_msg(text("我在~"))
