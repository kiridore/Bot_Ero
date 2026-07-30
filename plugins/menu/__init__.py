from core.base import CommandPlugin
from core.cq import text

from .bot_menu_text import BOT_MENU_TEXT


from core.utils import register_plugin
@register_plugin
class MenuPlugin(CommandPlugin):
    name = 'show_menu'
    description = '发送机器人功能菜单。'
    COMMANDS = ("/菜单", "/菜單")

    def handle(self):
        self.api.send_forward_msg([text(BOT_MENU_TEXT)])
