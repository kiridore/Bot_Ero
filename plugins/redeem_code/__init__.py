from core.base import CommandPlugin
from core.cq import at, text
from core.utils import register_plugin

MIGRATION_TIP = "兑换码功能已迁移至网页个人主页「兑换码」页签"


@register_plugin
class RedeemCodePlugin(CommandPlugin):
    """`/兑换码` 提示桩：撤回指令消息并引导至网页个人主页，防止兑换码在群聊明文暴露。

    兑换逻辑已全部在 webapp（1.58.0 迁移），本插件不读写数据库。
    """

    name = "redeem_code"
    description = "撤回 /兑换码 指令并提示该功能已迁移至网页个人主页。"

    COMMANDS = ("/兑换码", "/兌換碼")

    def handle(self):
        # 撤回尽力而为：失败（无群管理员/私聊）不影响提示发送
        if self.bot_event.message_id is not None:
            self.api.delete_msg(self.bot_event.message_id)
        if self.bot_event.user_id is not None:
            self.api.send_msg(at(self.bot_event.user_id), text(MIGRATION_TIP))
        else:
            self.api.send_msg(text(MIGRATION_TIP))
