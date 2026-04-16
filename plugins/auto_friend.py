from core.base import Plugin

class AutoFriendPlugin(Plugin):
    name = 'auto_accept_friend'
    description = '自动通过好友申请。'

    def match(self, message_type):
        if self.context.get("request_type", "") == "friend":
            return True
        return False

    def handle(self):
        flag = self.context["flag"]
        self.api.set_friend_add_request(flag)
