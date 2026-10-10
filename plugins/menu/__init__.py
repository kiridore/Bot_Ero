from core.base import CommandPlugin
from core.cq import text
import core.context as runtime_context

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
        uid = self.bot_event.user_id
        if (not in_group and uid is not None
                and runtime_context.registration_required()
                and not runtime_context.is_super_user(uid)):
            # 与准入检查同一套规则：未注册私聊菜单只显示注册与菜单条目（读不到状态时同样限显示）
            from core.database_manager import DbManager
            try:
                db = DbManager()
                try:
                    registered = db.community.is_registered(uid)
                finally:
                    db.conn.close()
            except Exception:
                registered = False
            if not registered:
                # 条目表内菜单行的插件标识是 "menu"（非插件键 show_menu），这里直接保留两行所需键
                enabled = {"register": enabled.get("register", False), "menu": True}
        self.api.send_forward_msg([text(render_menu(enabled, self.super_user(), in_group))])
