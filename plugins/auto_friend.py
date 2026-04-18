from core.base import Plugin

from core.utils import register_plugin
@register_plugin
class AutoFriendPlugin(Plugin):
    name = 'auto_accept_friend'
    description = '自动通过好友申请。'

    def match(self, message_type):
        if self.bot_event.request_type == "friend":
            return True
        return False

    def handle(self):
        flag = self.bot_event.raw["flag"]
        self.api.set_friend_add_request(flag)
