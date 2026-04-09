from core.base import Plugin
from core.cq import text

from .bot_menu_text import BOT_MENU_TEXT


class MenuPlugin(Plugin):
    def match(self, event_type):
        return self.on_full_match("/菜单")

    def handle(self):
        self.api.send_msg(text(BOT_MENU_TEXT))
