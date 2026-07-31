import re

from core.base import Plugin
from core.cq import text
from core.logger import logger
from core.utils import register_plugin
import core.context as runtime_context

from . import wizard as wiz
from . import character as char_logic
from .rules import ATTRIBUTES


@register_plugin
class TrpgCharPlugin(Plugin):
    name = "trpg_char"
    description = "DND 5E 角色卡：分步创建/查看/编辑/切换/删除"

    def _first_text(self) -> str:
        for seg in self.bot_event.message:
            if seg.get("type") == "text":
                return seg.get("data", {}).get("text", "").strip()
        return ""

    def _get_nickname(self) -> str:
        sender = self.bot_event.sender
        if sender and isinstance(sender, dict):
            return sender.get("card") or sender.get("nickname") or f"用户{self.bot_event.user_id}"
        return f"用户{self.bot_event.user_id}"

    def match(self, message_type) -> bool:
        if message_type != "message":
            return False
        msg = self._first_text()
        if not msg:
            return False
        if msg.startswith("/角色"):
            return True
        # 创建引导进行中：该用户所有消息都进入引导
        if self.bot_event.user_id and self.bot_event.user_id in runtime_context.character_wizards:
            return True
        return False

    def handle(self):
        try:
            user_id = self.bot_event.user_id
            msg = self._first_text()

            # 引导进行中，非 /角色 命令一律视为引导回复
            if user_id and user_id in runtime_context.character_wizards:
                if not msg.startswith("/角色"):
                    self._handle_wizard_reply(user_id, msg)
                    return

            if msg.startswith("/角色"):
                self._route_command(msg)
        except Exception:
            logger.exception("TrpgChar 处理异常")

    # ── 指令路由 ──────────────────────────────────────────

    def _route_command(self, msg: str):
        parts = msg.split()
        sub = parts[1] if len(parts) > 1 else ""

        if sub == "创建":
            self._handle_create()
        elif sub == "放弃":
            self._handle_abandon()
        elif sub == "编辑":
            self._handle_edit(parts[2:])
        elif sub == "切换":
            self._handle_switch(parts[2:])
        elif sub == "删除":
            self._handle_delete(parts[2:])
        elif sub == "列表":
            self._handle_list()
        elif sub == "查看" or not sub:
            self._handle_view(parts[2:])
        else:
            self._handle_view(parts[1:])

    # ── 创建引导 ──────────────────────────────────────────

    def _handle_create(self):
        user_id = self.bot_event.user_id
        if user_id is None:
            return
        if user_id in runtime_context.character_wizards:
            self.api.send_msg(text("已有进行中的角色创建，回复「退出」可放弃"))
            return
        state = wiz.start()
        runtime_context.character_wizards[user_id] = state
        self.api.send_msg(text(wiz.prompt(state)))

    def _handle_abandon(self):
        user_id = self.bot_event.user_id
        if user_id is None:
            return
        if runtime_context.character_wizards.pop(user_id, None):
            self.api.send_msg(text("已放弃角色创建"))
        else:
            self.api.send_msg(text("当前没有进行中的创建"))

    def _handle_wizard_reply(self, user_id: int, reply: str):
        state = runtime_context.character_wizards.get(user_id)
        if not state:
            return
        message, done, char_data = wiz.handle_reply(state, reply)
        if done:
            runtime_context.character_wizards.pop(user_id, None)
            if char_data:
                sheet = char_data.pop("_sheet", "")
                char_id = self.dbmanager.character.create(user_id, char_data)
                msg = f"角色创建成功！(#{char_id})\n{sheet}"
            else:
                msg = message
            self.api.send_msg(text(msg))
        else:
            self.api.send_msg(text(message))

    # ── 查看 ──────────────────────────────────────────

    def _handle_view(self, args: list):
        user_id = self.bot_event.user_id
        target_id = user_id
        for seg in self.bot_event.message:
            if seg.get("type") == "at":
                target_id = seg.get("data", {}).get("qq")
                break

        if target_id is None:
            return

        char_data = self.dbmanager.character.current(target_id)
        if not char_data:
            if target_id == user_id:
                self.api.send_msg(text("你还没有角色卡，用 /角色 创建 开始创建吧"))
            else:
                self.api.send_msg(text("该用户还没有角色卡"))
            return

        self.api.send_msg(text(char_logic.format_sheet(char_data)))

    # ── 列表/切换/删除 ──────────────────────────────────

    def _handle_list(self):
        user_id = self.bot_event.user_id
        if user_id is None:
            return
        chars = self.dbmanager.character.list_by_user(user_id)
        if not chars:
            self.api.send_msg(text("你还没有角色卡，用 /角色 创建 开始创建吧"))
            return
        current_id = self.dbmanager.character.current_id(user_id)
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
        char = self.dbmanager.character.get(char_id)
        if not char or str(char["user_id"]) != str(user_id):
            self.api.send_msg(text("角色不存在"))
            return
        self.dbmanager.character.set_current(user_id, char_id)
        self.api.send_msg(text(f"已将当前角色切换为 {char['char_name']}"))

    def _handle_delete(self, args: list):
        user_id = self.bot_event.user_id
        if user_id is None:
            return
        if not args or not args[0].lstrip("#").isdigit():
            self.api.send_msg(text("格式：/角色 删除 <编号>"))
            return
        char_id = int(args[0].lstrip("#"))
        char = self.dbmanager.character.get(char_id)
        if not char or str(char["user_id"]) != str(user_id):
            self.api.send_msg(text("角色不存在"))
            return
        self.dbmanager.character.delete(char_id)
        # 若删的是当前角色，自动切换
        if self.dbmanager.character.current_id(user_id) is None:
            rest = self.dbmanager.character.list_by_user(user_id)
            if rest:
                self.dbmanager.character.set_current(user_id, rest[0]["id"])
        self.api.send_msg(text(f"已删除角色 {char['char_name']}"))

    # ── 编辑 ──────────────────────────────────────────

    def _handle_edit(self, args: list):
        user_id = self.bot_event.user_id
        if user_id is None:
            return
        char = self.dbmanager.character.current(user_id)
        if not char:
            self.api.send_msg(text("你还没有角色卡，用 /角色 创建 开始创建吧"))
            return
        if len(args) < 2:
            self.api.send_msg(text(
                "格式：/角色 编辑 <字段> <值>\n"
                "可编辑字段：hp ac 力量 敏捷 体质 智力 感知 魅力 等级 备注\n"
                "备注可填特性/专长/物品等任意文本（例：/角色 编辑 备注 长弓、治疗药水×2、火球术卷轴）"
            ))
            return

        field = args[0]
        value = " ".join(args[1:])
        attr_map = {"力量": "str_score", "敏捷": "dex_score", "体质": "con_score",
                    "智力": "int_score", "感知": "wis_score", "魅力": "cha_score",
                    "备注": "notes"}
        db_field = attr_map.get(field, field)

        if db_field == "notes":
            self.dbmanager.character.update(char["id"], notes=value)
            self.api.send_msg(text(f"已更新 {field}"))
            return

        if db_field not in ("hp", "ac", "level", "str_score", "dex_score", "con_score",
                            "int_score", "wis_score", "cha_score"):
            self.api.send_msg(text(f"无法编辑字段 {field}，请检查格式"))
            return

        try:
            num = int(value)
            if num < 0 or (db_field.endswith("_score") and num > 30):
                raise ValueError
        except ValueError:
            self.api.send_msg(text(f"无法编辑字段 {field}，请检查格式"))
            return

        self.dbmanager.character.update(char["id"], **{db_field: num})

        # 属性变更后重新计算 HP/AC
        updated = self.dbmanager.character.get(char["id"])
        if updated and db_field.endswith("_score"):
            recalc = char_logic.finalize(updated)
            self.dbmanager.character.update(char["id"], hp=recalc["hp"], ac=recalc["ac"])
        self.api.send_msg(text(f"已更新 {field} 为 {value}"))
