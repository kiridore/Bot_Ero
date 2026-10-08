from core.base import CommandPlugin
from core.cq import text

from .entries import render_menu

from core.utils import register_plugin


@register_plugin
class MenuPlugin(CommandPlugin):
    name = 'show_menu'
    description = '发送机器人功能菜单。'
    COMMANDS = ("/菜单", "/菜單")

    def handle(self):
        # 按当前位置有效插件集合过滤：群聊查群设置，私聊查账号/公共默认（快照来自事件入口）
        enabled = dict(self.operation.enabled) if self.operation is not None else {}
        in_group = self.bot_event.group_id is not None
        self.api.send_forward_msg([text(render_menu(enabled, self.super_user(), in_group))])
