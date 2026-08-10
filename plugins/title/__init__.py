import random

from core.base import CommandPlugin
from core.cq import at, text
from core.utils import register_plugin

from .defs import TITLE_DEFS
from .logic import (
    evaluate_and_unlock_titles,
    get_title_def,
    get_lottery_title_ids,
    emit_title_unlock,
    _title_collection_progress,
)

__all__ = [
    "TITLE_DEFS",
    "get_title_def",
    "get_lottery_title_ids",
    "evaluate_and_unlock_titles",
    "emit_title_unlock",
    "TitlePlugin",
]


@register_plugin
class TitlePlugin(CommandPlugin):
    name = 'manage_titles'
    description = '查询、查看、装备和卸下称号。'
    COMMANDS = ("/称号一览", "/稱號一覽", "/称号", "/稱號")

    def _title_line(self, title_id, equipped_titles):
        data = TITLE_DEFS.get(title_id)
        if not data:
            return f"[{title_id}] 未知称号"
        suffix = "（已装备）" if title_id in equipped_titles else ""
        unlock_type = data.get("unlock_type", "unknown")
        return f"[{data['id']}] 「{data['name']}」 ({data['rarity']}, {unlock_type}){suffix}"

    def _get_target_user_id_from_at(self):
        for seg in self.bot_event.message:
            if seg.get("type") == "at":
                qq = seg.get("data", {}).get("qq")
                if qq and qq != "all":
                    return int(qq)
        return None

    def _show_title_list(self, user_id, show_to_user_id):
        title_ids = self.dbmanager.titles.list(user_id)
        equipped = set(self.dbmanager.titles.equipped_all(user_id))
        if not title_ids:
            self.api.send_msg(at(show_to_user_id), text("还没有解锁任何称号喵~"))
            return

        lines = [
            "已解锁称号：",
            f"搜集进度：{_title_collection_progress(len(title_ids), len(TITLE_DEFS))}",
            "",
        ]
        for tid in title_ids:
            lines.append(self._title_line(tid, equipped))
        self.api.send_forward_msg([text("\n".join(lines))])

    def _show_current(self, user_id):
        equipped = self.dbmanager.titles.equipped_all(user_id)
        if len(equipped) == 0:
            self.api.send_msg(at(user_id), text("你当前没有装备称号"))
            return
        lines = ["当前装备称号："]
        for tid in equipped:
            data = TITLE_DEFS.get(tid, {"name": "未知称号", "rarity": "unknown"})
            lines.append(f"[{tid}] 「{data['name']}」 ({data['rarity']})")
        self.api.send_msg(at(user_id), text("\n".join(lines)))

    def _show_detail(self, user_id, title_id):
        data = TITLE_DEFS.get(title_id)
        if not data:
            self.api.send_msg(at(user_id), text("没有这个称号编号喵"))
            return
        if not self.dbmanager.titles.has(user_id, title_id):
            self.api.send_msg(at(user_id), text("你还没有解锁这个称号喵"))
            return
        msg = f"[{data['id']}] 「{data['name']}」\n稀有度：{data['rarity']}\n说明：{data['description']}"
        self.api.send_msg(at(user_id), text(msg))

    def _send_unlocked_titles_notice(self, user_id, unlocked_ids):
        if not unlocked_ids:
            return
        lines = ["解锁新称号："]
        for tid in unlocked_ids:
            data = TITLE_DEFS.get(tid, {"name": "未知称号", "rarity": "unknown", "description": "无"})
            lines.append(f"[{tid}] 「{data['name']}」 ({data['rarity']}) - {data['description']}")
        self.api.send_msg(at(user_id), text("\n".join(lines)))

    def _equip(self, user_id, title_id):
        data = TITLE_DEFS.get(title_id)
        if not data:
            self.api.send_msg(at(user_id), text("没有这个称号编号喵"))
            return
        if not self.dbmanager.titles.has(user_id, title_id):
            self.api.send_msg(at(user_id), text("你还没有解锁这个称号喵"))
            return
        ok, reason = self.dbmanager.titles.equip(user_id, title_id, max_count=3)
        if not ok and reason == "already":
            self.api.send_msg(at(user_id), text(f"称号已装备：「{data['name']}」"))
            return
        if not ok and reason == "full":
            self.api.send_msg(at(user_id), text("最多只能装备3个称号，请先 /称号 卸下"))
            return
        unlocked = evaluate_and_unlock_titles(self.dbmanager, user_id)
        self._send_unlocked_titles_notice(user_id, unlocked)
        self.api.send_msg(at(user_id), text(f"已装备称号：「{data['name']}」"))

    def _unequip(self, user_id):
        self.dbmanager.titles.clear_equipped(user_id)
        unlocked = evaluate_and_unlock_titles(self.dbmanager, user_id)
        self._send_unlocked_titles_notice(user_id, unlocked)
        self.api.send_msg(at(user_id), text("已卸下所有装备称号"))

    def _equip_random(self, user_id):
        title_ids = self.dbmanager.titles.list(user_id)
        if not title_ids:
            self.api.send_msg(at(user_id), text("还没有可随机装备的称号喵"))
            return
        title_id = random.choice(title_ids)
        data = TITLE_DEFS.get(title_id, {"name": "未知称号"})
        ok, reason = self.dbmanager.titles.equip(user_id, title_id, max_count=3)
        if not ok and reason == "already":
            self.api.send_msg(at(user_id), text(f"随机到了已装备称号：[{title_id}] 「{data['name']}」"))
            return
        if not ok and reason == "full":
            self.api.send_msg(at(user_id), text("最多只能装备3个称号，请先 /称号 卸下"))
            return
        unlocked = evaluate_and_unlock_titles(self.dbmanager, user_id)
        self._send_unlocked_titles_notice(user_id, unlocked)
        self.api.send_msg(at(user_id), text(f"随机装备成功：[{title_id}] 「{data['name']}」"))

    def handle(self):
        if self.bot_event.user_id == None:
            return

        user_id = self.bot_event.user_id

        if self.cmd in ("/称号一览", "/稱號一覽"):
            self._show_title_list(user_id, user_id)
            return

        args = [a for a in self.args if a.strip() != ""]
        if len(args) == 0:
            self.api.send_msg(
                at(user_id),
                text("用法：/称号 当前 | /称号 卸下 | /称号 详情 <index> | /称号 随机 | /称号 <index> | /称号 查看 @用户（最多装备3个）"),
            )
            return

        sub = args[0]
        if sub in ("当前", "當前"):
            self._show_current(user_id)
            return
        if sub == "卸下":
            self._unequip(user_id)
            return
        if sub in ("随机", "隨機"):
            self._equip_random(user_id)
            return
        if sub in ("详情", "詳情"):
            if len(args) < 2 or not args[1].isdigit():
                self.api.send_msg(at(user_id), text("请使用 /称号 详情 <index>"))
                return
            self._show_detail(user_id, int(args[1]))
            return
        if sub in ("查看", "檢視"):
            target_user = self._get_target_user_id_from_at()
            if target_user is None:
                self.api.send_msg(at(user_id), text("请使用 /称号 查看 @用户"))
                return
            self._show_title_list(target_user, user_id)
            return

        if sub.isdigit():
            self._equip(user_id, int(sub))
            return

        self.api.send_msg(at(user_id), text("无法识别的子命令喵"))