from core.base import Plugin
from core.cq import text

class WelcomePlugin(Plugin):
    def match(self):
        if self.context.get("request_type", "") == "friend_add":
            return True
        return False

    def handle(self):
        self.send_private_msg(text("感谢订阅小埃同学私人打卡服务喵~\n 使用指令“菜单”即可查看所有可用功能"))
