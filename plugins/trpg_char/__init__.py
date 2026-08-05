import os

from core.base import Plugin
from core.cq import text
from core.logger import logger
from core.utils import register_plugin

from core import character_store as store
from . import character as char_logic

WEB_TRPG_URL = os.environ.get("BOTERO_WEB_URL", "https://trpg.littlero.com")


@register_plugin
class TrpgCharPlugin(Plugin):
    name = "trpg_char"
    description = "DND 5E 角色卡：查看/列表/切换/删除（创建与编辑请到网页端）"

    def _first_text(self) -> str:
        for seg in self.bot_event.message:
            if seg.get("type") == "text":
                return seg.get("data", {}).get("text", "").strip()
        return ""

    def match(self, message_type) -> bool:
        if message_type != "message":
            return False
        return self._first_text().startswith("/角色")

    def handle(self):
        try:
            msg = self._first_text()
            if msg.startswith("/角色"):
                self._route_command(msg)
        except Exception:
            logger.exception("TrpgChar 处理异常")

    def _route_command(self, msg: str):
        parts = msg.split()
        sub = parts[1] if len(parts) > 1 else ""
        if sub in ("创建", "编辑", "放弃"):
            self.api.send_msg(text(
                "角色卡的创建与编辑已迁移到网页端：\n" + WEB_TRPG_URL
            ))
        elif sub == "切换":
            self._handle_switch(parts[2:])
        elif sub == "删除":
            self._handle_delete(parts[2:])
        elif sub == "列表":
            self._handle_list()
        else:
            self._handle_view()

    def _handle_view(self):
        user_id = self.bot_event.user_id
        if user_id is None:
            return
        char_data = store.get_current(user_id)
        if not char_data:
            self.api.send_msg(text("你还没有角色卡，请到网页端创建：\n" + WEB_TRPG_URL))
            return
        self.api.send_msg(text(char_logic.format_sheet(char_data)))

    def _handle_list(self):
        user_id = self.bot_event.user_id
        if user_id is None:
            return
        chars = store.list_chars(user_id)
        if not chars:
            self.api.send_msg(text("你还没有角色卡，请到网页端创建：\n" + WEB_TRPG_URL))
            return
        current = store.get_current(user_id)
        current_id = current["id"] if current else None
        lines = ["你的角色卡："]
        for c in chars:
            mark = " ◀ 当前" if c["id"] == current_id else ""
            lines.append(f"#{c['id']} {c['char_name']} Lv.{c['level']} {c['race']} {c['class_name']}{mark}")
        self.api.send_msg(text("\n".join(lines)))

    def _handle_switch(self, args: list):
        user_id = self.bot_event.user_id
        if user_id is None:
            return
        if not args or not args[0].lstrip("#").isdigit():
            self.api.send_msg(text("格式：/角色 切换 <编号>"))
            return
        char_id = int(args[0].lstrip("#"))
        try:
            store.set_current(user_id, char_id)
        except ValueError:
            self.api.send_msg(text("角色不存在"))
            return
        char = store.get_char(user_id, char_id)
        if not char:
            return
        self.api.send_msg(text(f"已将当前角色切换为 {char['char_name']}"))

    def _handle_delete(self, args: list):
        user_id = self.bot_event.user_id
        if user_id is None:
            return
        if not args or not args[0].lstrip("#").isdigit():
            self.api.send_msg(text("格式：/角色 删除 <编号>"))
            return
        char_id = int(args[0].lstrip("#"))
        char = store.get_char(user_id, char_id)
        if not char:
            self.api.send_msg(text("角色不存在"))
            return
        store.delete_char(user_id, char_id)
        self.api.send_msg(text(f"已删除角色 {char['char_name']}"))
