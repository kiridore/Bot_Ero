from core.base import Plugin
from core.cq import at, text

from core.utils import register_plugin
@register_plugin
class GroupSpecialTitlePlugin(Plugin):
    name = 'set_group_special_title'
    description = '设置或清空用户群头衔。'

    def match(self, message_type):
        return self.on_command("/群头衔")

    def handle(self):
        raw_data = self.bot_event.message[0]

        if raw_data['type'] != 'text':
            return

        msg = raw_data['data']['text']
        args = msg.split(" ")
        title = ""

        if len(args) > 1:
            title = args[1]

        if title == "":
            self.api.send_msg(text("给"), at(self.bot_event.user_id), text("取消头衔了喵~"))
            self.api.set_group_special_title(self.bot_event.group_id, self.bot_event.user_id, title)
        elif len(title) > 10:
            self.api.send_msg(text("头衔太长了喵，最多只能十个字符长"))
        else:
            self.api.send_msg(text("给"), at(self.bot_event.user_id), text("设置了新头衔喵~"))
            self.api.set_group_special_title(self.bot_event.group_id, self.bot_event.user_id, title)

        return
