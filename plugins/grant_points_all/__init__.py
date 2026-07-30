from core.base import CommandPlugin
from core.cq import text


from core.utils import register_plugin
@register_plugin
class GrantPointsAllPlugin(CommandPlugin):
    name = 'grant_points_all'
    description = '给全部用户统一发放积分。'
    COMMANDS = ("/发金币", "/發金幣")

    def match(self, event_type="message"):
        return self.admin_user() and super().match(event_type)

    def handle(self):
        if len(self.args) < 1:
            self.api.send_msg(text("请使用 /发金币 <积分数量>"))
            return

        try:
            amount = int(self.args[0])
        except Exception:
            self.api.send_msg(text("积分数量必须是整数喵"))
            return

        if amount == 0:
            self.api.send_msg(text("发0点就不要折腾我了喵"))
            return

        user_count = self.dbmanager.points.grant_all(amount)
        self.api.send_msg(text("已给 {} 位用户发放 {} 点积分".format(user_count, amount)))
