from core.base import Plugin
from core.cq import text


class GrantPointsAllPlugin(Plugin):
    def match(self, message_type):
        return self.admin_user() and self.on_command("/发金币")

    def handle(self):
        if len(self.args) < 2:
            self.api.send_msg(text("请使用 /发金币 <积分数量>"))
            return

        try:
            amount = int(self.args[1])
        except Exception:
            self.api.send_msg(text("积分数量必须是整数喵"))
            return

        if amount == 0:
            self.api.send_msg(text("发0点就不要折腾我了喵"))
            return

        user_count = self.dbmanager.grant_points_to_all_users(amount)
        self.api.send_msg(text("已给 {} 位用户发放 {} 点积分".format(user_count, amount)))
