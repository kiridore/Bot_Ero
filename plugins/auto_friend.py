from core.base import Plugin
from core.cq import text

class AutoFriendPlugin(Plugin):
    def match(self):
        if self.context.get("request_type", "") == "friend":
            return True

    def handle(self):
        flag = self.context["flag"]
        self.set_friend_add_request(flag)
        self.send_private_msg(text("感谢订阅小埃同学私人打卡服务喵~\n 使用指令“菜单”即可查看所有可用功能"))
