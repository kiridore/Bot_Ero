import random

from core.base import Plugin
from core.cq import at, text


TITLE_DEFS = {
    # common
    1: {"id": 1, "name": "幸运星", "rarity": "common", "description": "运气不错，但这是普通称号", "unlock_type": "lottery"},
    2: {"id": 2, "name": "凡人", "rarity": "common", "description": "普通人", "unlock_type": "lottery"},
    3: {"id": 3, "name": "狂人", "rarity": "common", "description": "村人没有售价，狂人入口即化", "unlock_type": "lottery"},
    4: {"id": 4, "name": "乌鸦", "rarity": "common", "description": "亮闪闪！亮闪闪！", "unlock_type": "lottery"},
    5: {"id": 5, "name": "黑", "rarity": "common", "description": "黑", "unlock_type": "lottery"},
    6: {"id": 6, "name": "白", "rarity": "common", "description": "白", "unlock_type": "lottery"},
    7: {"id": 7, "name": "ERROR", "rarity": "common", "description": "ERROR", "unlock_type": "lottery"},
    8: {"id": 8, "name": "苟活", "rarity": "common", "description": "狂人不会苟活", "unlock_type": "lottery"},
    9: {"id": 9, "name": "驾崩", "rarity": "common", "description": "君主离线了", "unlock_type": "lottery"},
    10: {"id": 10, "name": "猫", "rarity": "common", "description": "时而出现，时而消失。", "unlock_type": "lottery"},
    11: {"id": 11, "name": "咕", "rarity": "common", "description": "可能稍后出现。", "unlock_type": "lottery"},
    12: {"id": 12, "name": "摆", "rarity": "common", "description": "深谙放松之道。", "unlock_type": "lottery"},
    13: {"id": 13, "name": "摸", "rarity": "common", "description": "难以预测。", "unlock_type": "lottery"},
    14: {"id": 14, "name": "不想", "rarity": "common", "description": "单纯不想", "unlock_type": "lottery"},
    15: {"id": 15, "name": "上班", "rarity": "common", "description": "真有人会单独用这个吗", "unlock_type": "lottery"},
    16: {"id": 16, "name": "重生", "rarity": "common", "description": "活了", "unlock_type": "lottery"},
    17: {"id": 17, "name": "狂热", "rarity": "common", "description": "From Werwolf", "unlock_type": "lottery"},
    18: {"id": 18, "name": "魔女", "rarity": "common", "description": "From Werwolf", "unlock_type": "lottery"},
    19: {"id": 19, "name": "狼人", "rarity": "common", "description": "From Werwolf", "unlock_type": "lottery"},
    20: {"id": 20, "name": "宠物", "rarity": "common", "description": "From Werwolf", "unlock_type": "lottery"},
    21: {"id": 21, "name": "猎人", "rarity": "common", "description": "From Werwolf", "unlock_type": "lottery"},
    22: {"id": 22, "name": "咒杀", "rarity": "common", "description": "From Werwolf", "unlock_type": "lottery"},
    23: {"id": 23, "name": "剑术士", "rarity": "common", "description": "剑术小b", "unlock_type": "lottery"},
    24: {"id": 24, "name": "斧术师", "rarity": "common", "description": "斧头小b", "unlock_type": "lottery"},
    25: {"id": 25, "name": "枪术士", "rarity": "common", "description": "枪术小b", "unlock_type": "lottery"},
    26: {"id": 26, "name": "格斗家", "rarity": "common", "description": "格斗小b", "unlock_type": "lottery"},
    27: {"id": 27, "name": "双剑师", "rarity": "common", "description": "NINJA小b", "unlock_type": "lottery"},
    28: {"id": 28, "name": "弓箭手", "rarity": "common", "description": "弓箭小b", "unlock_type": "lottery"},
    29: {"id": 29, "name": "⚀", "rarity": "common", "description": "骰子的一个侧面", "unlock_type": "lottery"},
    30: {"id": 30, "name": "⚁", "rarity": "common", "description": "骰子的一个侧面", "unlock_type": "lottery"},
    31: {"id": 31, "name": "⚂", "rarity": "common", "description": "骰子的一个侧面", "unlock_type": "lottery"},
    32: {"id": 32, "name": "⚃", "rarity": "common", "description": "骰子的一个侧面", "unlock_type": "lottery"},
    33: {"id": 33, "name": "⚄", "rarity": "common", "description": "骰子的一个侧面", "unlock_type": "lottery"},
    34: {"id": 34, "name": "⚅", "rarity": "common", "description": "骰子的一个侧面", "unlock_type": "lottery"},
    35: {"id": 35, "name": "🧀", "rarity": "common", "description": "魔法芝士的一个侧面", "unlock_type": "lottery"},
    36: {"id": 36, "name": "控", "rarity": "common", "description": "__ __ __ __ 控", "unlock_type": "lottery"},
    37: {"id": 37, "name": "兔子", "rarity": "common", "description": "兔子，兔子，兔子", "unlock_type": "lottery"},
    38: {"id": 38, "name": "明日", "rarity": "common", "description": "明日复明日", "unlock_type": "lottery"},
    39: {"id": 39, "name": "方舟", "rarity": "common", "description": "永续的方舟", "unlock_type": "lottery"},
    40: {"id": 40, "name": "君主", "rarity": "common", "description": "至高权力之人（仅限称号）", "unlock_type": "lottery"},

    # rare
    41: {"id": 41, "name": "卷", "rarity": "rare", "description": "你似乎无法停止前进。", "unlock_type": "lottery"},
    42: {"id": 42, "name": "稳", "rarity": "rare", "description": "一切似乎都在掌控之中。", "unlock_type": "lottery"},
    43: {"id": 43, "name": "光之战士", "rarity": "rare", "description": "倾听，感受，思考", "unlock_type": "lottery"},
    44: {"id": 44, "name": "伟大的黑魔法师", "rarity": "rare", "description": "对，伟大的黑魔法师！", "unlock_type": "lottery"},
    45: {"id": 45, "name": "永远不死", "rarity": "rare", "description": "我死不了了", "unlock_type": "lottery"},
    46: {"id": 46, "name": "享受者", "rarity": "rare", "description": "享受一切", "unlock_type": "lottery"},
    47: {"id": 47, "name": "骑士", "rarity": "rare", "description": "自由骑士的誓约", "unlock_type": "lottery"},
    48: {"id": 48, "name": "战士", "rarity": "rare", "description": "责任与使命", "unlock_type": "lottery"},
    49: {"id": 49, "name": "暗黑骑士", "rarity": "rare", "description": "来自深渊", "unlock_type": "lottery"},
    50: {"id": 50, "name": "绝枪战士", "rarity": "rare", "description": "海王，海王，海王", "unlock_type": "lottery"},

    # legendary
    51: {"id": 51, "name": "我还没有睡饱", "rarity": "legendary", "description": "定型文", "unlock_type": "lottery"},
    52: {"id": 52, "name": "重生之境", "rarity": "legendary", "description": "2.0", "unlock_type": "lottery"},
    53: {"id": 53, "name": "苍穹之禁城", "rarity": "legendary", "description": "3.0", "unlock_type": "lottery"},
    54: {"id": 54, "name": "最好的学生", "rarity": "legendary", "description": "<<最好的学生>>", "unlock_type": "lottery"},
    55: {"id": 55, "name": "人人网", "rarity": "legendary", "description": "你人人网", "unlock_type": "lottery"},
    56: {"id": 56, "name": "母肥", "rarity": "legendary", "description": "谁不喜欢母肥呢", "unlock_type": "lottery"},
    57: {"id": 57, "name": "男精", "rarity": "legendary", "description": "谁不喜欢男精呢", "unlock_type": "lottery"},
    58: {"id": 58, "name": "龙娘", "rarity": "legendary", "description": "谁不喜欢龙娘呢", "unlock_type": "lottery"},
    59: {"id": 59, "name": "龙男", "rarity": "legendary", "description": "谁不喜欢龙男呢", "unlock_type": "lottery"},
}



def get_title_def(title_id):
    return TITLE_DEFS.get(title_id)


def get_lottery_title_ids():
    return [tid for tid, data in TITLE_DEFS.items() if data.get("unlock_type") == "lottery"]


class TitlePlugin(Plugin):
    def match(self, message_type):
        if self.on_full_match("/称号一览"):
            return True
        return self.on_command("/称号")

    def _title_line(self, title_id, equipped_titles):
        data = TITLE_DEFS.get(title_id)
        if not data:
            return f"[{title_id}] 未知称号"
        suffix = "（已装备）" if title_id in equipped_titles else ""
        unlock_type = data.get("unlock_type", "unknown")
        return f"[{data['id']}] 「{data['name']}」 ({data['rarity']}, {unlock_type}){suffix}"

    def _get_target_user_id_from_at(self):
        for seg in self.context.get("message", []):
            if seg.get("type") == "at":
                qq = seg.get("data", {}).get("qq")
                if qq and qq != "all":
                    return int(qq)
        return None

    def _show_title_list(self, user_id, show_to_user_id):
        title_ids = self.dbmanager.get_user_titles(user_id)
        equipped = set(self.dbmanager.get_equipped_titles(user_id))
        if not title_ids:
            self.api.send_msg(at(show_to_user_id), text("还没有解锁任何称号喵~"))
            return

        lines = ["已解锁称号：", ""]
        for tid in title_ids:
            lines.append(self._title_line(tid, equipped))
        self.api.send_msg(at(show_to_user_id), text("\n".join(lines)))

    def _show_current(self, user_id):
        equipped = self.dbmanager.get_equipped_titles(user_id)
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
        if not self.dbmanager.has_title(user_id, title_id):
            self.api.send_msg(at(user_id), text("你还没有解锁这个称号喵"))
            return
        msg = f"[{data['id']}] 「{data['name']}」\n稀有度：{data['rarity']}\n说明：{data['description']}"
        self.api.send_msg(at(user_id), text(msg))

    def _equip(self, user_id, title_id):
        data = TITLE_DEFS.get(title_id)
        if not data:
            self.api.send_msg(at(user_id), text("没有这个称号编号喵"))
            return
        if not self.dbmanager.has_title(user_id, title_id):
            self.api.send_msg(at(user_id), text("你还没有解锁这个称号喵"))
            return
        ok, reason = self.dbmanager.equip_title(user_id, title_id, max_count=3)
        if not ok and reason == "already":
            self.api.send_msg(at(user_id), text(f"称号已装备：「{data['name']}」"))
            return
        if not ok and reason == "full":
            self.api.send_msg(at(user_id), text("最多只能装备3个称号，请先 /称号 卸下"))
            return
        self.api.send_msg(at(user_id), text(f"已装备称号：「{data['name']}」"))

    def _unequip(self, user_id):
        self.dbmanager.clear_equipped_titles(user_id)
        self.api.send_msg(at(user_id), text("已卸下所有装备称号"))

    def _equip_random(self, user_id):
        title_ids = self.dbmanager.get_user_titles(user_id)
        if not title_ids:
            self.api.send_msg(at(user_id), text("还没有可随机装备的称号喵"))
            return
        title_id = random.choice(title_ids)
        data = TITLE_DEFS.get(title_id, {"name": "未知称号"})
        ok, reason = self.dbmanager.equip_title(user_id, title_id, max_count=3)
        if not ok and reason == "already":
            self.api.send_msg(at(user_id), text(f"随机到了已装备称号：[{title_id}] 「{data['name']}」"))
            return
        if not ok and reason == "full":
            self.api.send_msg(at(user_id), text("最多只能装备3个称号，请先 /称号 卸下"))
            return
        self.api.send_msg(at(user_id), text(f"随机装备成功：[{title_id}] 「{data['name']}」"))

    def handle(self):
        user_id = self.context["user_id"]

        if self.on_full_match("/称号一览"):
            self._show_title_list(user_id, user_id)
            return

        args = [a for a in self.args if a.strip() != ""]
        if len(args) == 1:
            self.api.send_msg(
                at(user_id),
                text("用法：/称号 当前 | /称号 卸下 | /称号 详情 <index> | /称号 随机 | /称号 <index> | /称号 查看 @用户（最多装备3个）"),
            )
            return

        sub = args[1]
        if sub == "当前":
            self._show_current(user_id)
            return
        if sub == "卸下":
            self._unequip(user_id)
            return
        if sub == "随机":
            self._equip_random(user_id)
            return
        if sub == "详情":
            if len(args) < 3 or not args[2].isdigit():
                self.api.send_msg(at(user_id), text("请使用 /称号 详情 <index>"))
                return
            self._show_detail(user_id, int(args[2]))
            return
        if sub == "查看":
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
