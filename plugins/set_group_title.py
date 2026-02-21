from core.base import Plugin
from core.cq import at, text

class GroupSpecialTitlePlugin(Plugin):
    def match(self):
        return self.on_command("/群头衔")

    def handle(self):
        raw_data = self.context["message"][0]

        if raw_data['type'] != 'text':
            return

        msg = raw_data['data']['text']
        args = msg.split(" ")
        title = ""

        if len(args) > 1:
            title = args[1]

        if title == "":
            self.api.send_msg(text("给"), at(self.context["user_id"]), text("取消头衔了喵~"))
            self.api.set_group_special_title(self.context["group_id"], self.context["user_id"], title)
        elif len(title) > 10:
            self.api.send_msg(text("头衔太长了喵，最多只能十个字符长"))
        else:
            self.api.send_msg(text("给"), at(self.context["user_id"]), text("设置了新头衔喵~"))
            self.api.set_group_special_title(self.context["group_id"], self.context["user_id"], title)

        return
