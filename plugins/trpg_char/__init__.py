from core.base import Plugin
from core.config import WEB_BASE_URL
from core.cq import text
from core.logger import logger
from core.utils import register_plugin

from core import character_store as store
from core.trpg import coc as coc_sheet
from . import character as char_logic

WEB_TRPG_URL = f"{WEB_BASE_URL}/trpg"
COMMAND = "/跑团"


@register_plugin
class TrpgCharPlugin(Plugin):
    name = "trpg_char"
    description = "DND 5E 角色卡：查看/列表/切换/删除（创建与编辑请到网页端）"

    def _first_text(self) -> str:
        for seg in self.bot_event.message:
            if seg.get("type") == "text":
                return seg.get("data", {}).get("text", "").strip()
        return ""

    def _command_parts(self):
        parts = self._first_text().split()
        if len(parts) < 2 or parts[0] != COMMAND or parts[1] != "角色":
            return None
        return parts

    def match(self, message_type) -> bool:
        if message_type != "message":
            return False
        return self._command_parts() is not None

    def handle(self):
        try:
            parts = self._command_parts()
            if parts is not None:
                self._route_command(parts)
        except Exception:
            logger.exception("TrpgChar 处理异常")

    def _route_command(self, parts: list):
        sub = parts[2] if len(parts) > 2 else ""
        if sub in ("创建", "编辑", "放弃"):
            self.api.send_msg(text(
                "角色卡的创建与编辑已迁移到网页端：\n" + WEB_TRPG_URL
            ))
        elif sub == "切换":
            self._handle_switch(parts[3:])
        elif sub == "删除":
            self._handle_delete(parts[3:])
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
            if (c.get("rules") or "dnd5e") == "coc7th":
                lines.append(f"#{c['id']} {c['char_name']} COC 调查员 {c.get('occupation') or ''}{mark}")
            else:
                lines.append(f"#{c['id']} {c['char_name']} Lv.{c['level']} {c['race']} {c['class_name']}{mark}")
        self.api.send_msg(text("\n".join(lines)))

    def _handle_switch(self, args: list):
        user_id = self.bot_event.user_id
        if user_id is None:
            return
        if not args or not args[0].lstrip("#").isdigit():
            self.api.send_msg(text("格式：/跑团 角色 切换 <编号>"))
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
            self.api.send_msg(text("格式：/跑团 角色 删除 <编号>"))
            return
        char_id = int(args[0].lstrip("#"))
        char = store.get_char(user_id, char_id)
        if not char:
            self.api.send_msg(text("角色不存在"))
            return
        store.delete_char(user_id, char_id)
        self.api.send_msg(text(f"已删除角色 {char['char_name']}"))
