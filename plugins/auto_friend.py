from core.base import Plugin

class AutoFriendPlugin(Plugin):
    def match(self):
        if self.context.get("request_type", "") == "friend":
            return True
        return False

    def handle(self):
        flag = self.context["flag"]
        self.set_friend_add_request(flag)
