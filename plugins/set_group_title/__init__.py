from core.base import CommandPlugin
from core.cq import at, text

from core.utils import register_plugin
@register_plugin
class GroupSpecialTitlePlugin(CommandPlugin):
    name = 'set_group_special_title'
    description = '设置或清空用户群头衔。'
    COMMANDS = ("/群头衔", "/群頭銜")

    def handle(self):
        if self.bot_event.user_id == None:
            return

        title = self.args[0] if len(self.args) > 0 else ""

        if title == "":
            self.api.send_msg(text("给"), at(self.bot_event.user_id), text("取消头衔了喵~"))
            self.api.set_group_special_title(self.bot_event.group_id, self.bot_event.user_id, title)
        elif len(title) > 10:
            self.api.send_msg(text("头衔太长了喵，最多只能十个字符长"))
        else:
            self.api.send_msg(text("给"), at(self.bot_event.user_id), text("设置了新头衔喵~"))
            self.api.set_group_special_title(self.bot_event.group_id, self.bot_event.user_id, title)

        return
