from core.base import Plugin
from core.cq import at, text

class GroupSpecialTitlePlugin(Plugin):
    def match(self):
        msg:str = self.context["message"][0]
        if msg.startswith("/群头衔"):
            return True
        else:
            return False

    def handle(self):
        msg:str = self.context["message"][0]
        args = msg.split(" ")
        title = ""

        if len(args) > 1:
            title = args[1]

        if title == "":
            self.send_msg(text("给"), at(self.context["user_id"]), text("取消头衔了喵~"))
            self.set_group_special_title(self.context["group_id"], self.context["user_id"], title)
        elif len(title) > 10:
            self.send_msg(text("头衔太长了喵，最多只能十个字符长"))
        else:
            self.send_msg(text("给"), at(self.context["user_id"]), text("设置了新头衔喵~"))
            self.set_group_special_title(self.context["group_id"], self.context["user_id"], title)
        pass
