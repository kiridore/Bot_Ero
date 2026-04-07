import random
from datetime import datetime, timedelta

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
    23: {"id": 23, "name": "剑术士", "rarity": "common", "description": "剑术士的基础", "unlock_type": "lottery"},
    24: {"id": 24, "name": "斧术师", "rarity": "common", "description": "斧术师的基础", "unlock_type": "lottery"},
    25: {"id": 25, "name": "枪术士", "rarity": "common", "description": "枪术士的基础", "unlock_type": "lottery"},
    26: {"id": 26, "name": "格斗家", "rarity": "common", "description": "格斗家的基础", "unlock_type": "lottery"},
    27: {"id": 27, "name": "双剑师", "rarity": "common", "description": "双剑师的基础", "unlock_type": "lottery"},
    28: {"id": 28, "name": "弓箭手", "rarity": "common", "description": "弓箭手的基础", "unlock_type": "lottery"},
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
    49: {"id": 49, "name": "暗黑骑士", "rarity": "rare", "description": "暗黑之力", "unlock_type": "lottery"},
    50: {"id": 50, "name": "绝枪战士", "rarity": "rare", "description": "枪刃启程", "unlock_type": "lottery"},

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
    60: {"id": 60, "name": "白魔法师", "rarity": "rare", "description": "自然之怒", "unlock_type": "lottery"},
    61: {"id": 61, "name": "学者", "rarity": "rare", "description": "失落的学问", "unlock_type": "lottery"},
    62: {"id": 62, "name": "占星术士", "rarity": "rare", "description": "命运之轮", "unlock_type": "lottery"},
    63: {"id": 63, "name": "贤者", "rarity": "rare", "description": "贤者之路", "unlock_type": "lottery"},
    64: {"id": 64, "name": "武僧", "rarity": "rare", "description": "愤怒的拳", "unlock_type": "lottery"},
    65: {"id": 65, "name": "龙骑士", "rarity": "rare", "description": "苍穹骑士", "unlock_type": "lottery"},
    66: {"id": 66, "name": "忍者", "rarity": "rare", "description": "无形的刃", "unlock_type": "lottery"},
    67: {"id": 67, "name": "武士", "rarity": "rare", "description": "武士之道", "unlock_type": "lottery"},
    68: {"id": 68, "name": "钐镰客", "rarity": "rare", "description": "死神的邀约", "unlock_type": "lottery"},
    69: {"id": 69, "name": "蝰蛇剑士", "rarity": "rare", "description": "双刃初啼", "unlock_type": "lottery"},
    70: {"id": 70, "name": "吟游诗人", "rarity": "rare", "description": "诗与弓", "unlock_type": "lottery"},
    71: {"id": 71, "name": "机工士", "rarity": "rare", "description": "火花与钢铁", "unlock_type": "lottery"},
    72: {"id": 72, "name": "舞者", "rarity": "rare", "description": "舞动的灵魂", "unlock_type": "lottery"},
    73: {"id": 73, "name": "黑魔法师", "rarity": "rare", "description": "黑魔法的传承", "unlock_type": "lottery"},
    74: {"id": 74, "name": "召唤师", "rarity": "rare", "description": "唤醒以太", "unlock_type": "lottery"},
    75: {"id": 75, "name": "赤魔法师", "rarity": "rare", "description": "赤之誓言", "unlock_type": "lottery"},
    76: {"id": 76, "name": "青魔法师", "rarity": "rare", "description": "非常规的魔法", "unlock_type": "lottery"},
    77: {"id": 77, "name": "绘灵法师", "rarity": "rare", "description": "色彩与想象", "unlock_type": "lottery"},
    78: {"id": 78, "name": "刻木匠", "rarity": "common", "description": "刻木匠的基础", "unlock_type": "lottery"},
    79: {"id": 79, "name": "锻铁匠", "rarity": "common", "description": "锻铁匠的基础", "unlock_type": "lottery"},
    80: {"id": 80, "name": "铸甲匠", "rarity": "common", "description": "铸甲匠的基础", "unlock_type": "lottery"},
    81: {"id": 81, "name": "雕金匠", "rarity": "common", "description": "雕金匠的基础", "unlock_type": "lottery"},
    82: {"id": 82, "name": "制革匠", "rarity": "common", "description": "制革匠的基础", "unlock_type": "lottery"},
    83: {"id": 83, "name": "裁衣匠", "rarity": "common", "description": "裁衣匠的基础", "unlock_type": "lottery"},
    84: {"id": 84, "name": "炼金术士", "rarity": "common", "description": "炼金术士的基础", "unlock_type": "lottery"},
    85: {"id": 85, "name": "烹调师", "rarity": "common", "description": "烹调师的基础", "unlock_type": "lottery"},
    86: {"id": 86, "name": "采矿工", "rarity": "common", "description": "采矿工的基础", "unlock_type": "lottery"},
    87: {"id": 87, "name": "园艺工", "rarity": "common", "description": "园艺工的基础", "unlock_type": "lottery"},
    88: {"id": 88, "name": "捕鱼人", "rarity": "common", "description": "捕鱼人的基础", "unlock_type": "lottery"},
    89: {"id": 89, "name": "幻术师", "rarity": "common", "description": "治疗之芽", "unlock_type": "lottery"},
    90: {"id": 90, "name": "咒术师", "rarity": "common", "description": "灾厄之芽", "unlock_type": "lottery"},
    91: {"id": 91, "name": "秘术师", "rarity": "common", "description": "知识之芽", "unlock_type": "lottery"},

    # condition: 打卡时段/日期/进度
    201: {"id": 201, "name": "早起的鸟儿", "rarity": "common", "description": "在早上8点到12点完成打卡", "unlock_type": "condition"},
    202: {"id": 202, "name": "下午茶", "rarity": "common", "description": "在下午2点到下午4点完成打卡", "unlock_type": "condition"},
    203: {"id": 203, "name": "我下班了", "rarity": "common", "description": "在下午5:30到6:30完成打卡", "unlock_type": "condition"},
    204: {"id": 204, "name": "熬夜冠军", "rarity": "rare", "description": "在凌晨1点到5点完成打卡", "unlock_type": "condition"},
    205: {"id": 205, "name": "压哨冲线", "rarity": "rare", "description": "在周日23:30到周一8:00完成打卡", "unlock_type": "condition"},
    206: {"id": 206, "name": "不休息的板油", "rarity": "legendary", "description": "累计打卡365天", "unlock_type": "condition"},
    207: {"id": 207, "name": "打卡收藏家", "rarity": "rare", "description": "累计打卡200天", "unlock_type": "condition"},
    208: {"id": 208, "name": "时间管理大师", "rarity": "rare", "description": "累计打卡100天", "unlock_type": "condition"},
    209: {"id": 209, "name": "规律作息", "rarity": "common", "description": "累计打卡30天", "unlock_type": "condition"},
    210: {"id": 210, "name": "日界线", "rarity": "rare", "description": "在23:59到00:01打卡", "unlock_type": "condition"},
    211: {"id": 211, "name": "刚刚好", "rarity": "rare", "description": "在00:00打卡", "unlock_type": "condition"},
    212: {"id": 212, "name": "劳动模范", "rarity": "common", "description": "在5月1日打卡", "unlock_type": "condition"},
    213: {"id": 213, "name": "愚者", "rarity": "common", "description": "在4月1日打卡", "unlock_type": "condition"},
    214: {"id": 214, "name": "小孩", "rarity": "common", "description": "在6月1日打卡", "unlock_type": "condition"},
    215: {"id": 215, "name": "程序员", "rarity": "common", "description": "在10月24日打卡", "unlock_type": "condition"},
    216: {"id": 216, "name": "Neko", "rarity": "rare", "description": "在2月22日打卡", "unlock_type": "condition"},
    217: {"id": 217, "name": "画画更重要", "rarity": "common", "description": "在2月14日打卡", "unlock_type": "condition"},
    218: {"id": 218, "name": "我在~", "rarity": "rare", "description": "在8月11日打卡", "unlock_type": "condition"},
    219: {"id": 219, "name": "圆周率", "rarity": "common", "description": "在3月14日打卡", "unlock_type": "condition"},
    220: {"id": 220, "name": "回响", "rarity": "rare", "description": "在A-A格式日期打卡", "unlock_type": "condition"},
    221: {"id": 221, "name": "新年", "rarity": "common", "description": "在1月1日打卡", "unlock_type": "condition"},
    222: {"id": 222, "name": "搜集", "rarity": "common", "description": "累计解锁10个称号", "unlock_type": "condition"},
    223: {"id": 223, "name": "研究员", "rarity": "rare", "description": "累计解锁20个称号", "unlock_type": "condition"},
    224: {"id": 224, "name": "造物院", "rarity": "legendary", "description": "累计解锁30个称号", "unlock_type": "condition"},
    225: {"id": 225, "name": "金色", "rarity": "legendary", "description": "获得一个传说品质称号", "unlock_type": "condition"},
    226: {"id": 226, "name": "小金人", "rarity": "legendary", "description": "三个称号栏都装备传说品质称号", "unlock_type": "condition"},
    227: {"id": 227, "name": "重复观测", "rarity": "common", "description": "抽到1次重复称号", "unlock_type": "condition"},
    228: {"id": 228, "name": "古典概型", "rarity": "rare", "description": "抽到10次重复称号", "unlock_type": "condition"},
    229: {"id": 229, "name": "正态分布", "rarity": "legendary", "description": "抽到100次重复称号", "unlock_type": "condition"},
    230: {"id": 230, "name": "试试", "rarity": "common", "description": "累计抽奖1次", "unlock_type": "condition"},
    231: {"id": 231, "name": "玩", "rarity": "common", "description": "累计抽奖10次", "unlock_type": "condition"},
    232: {"id": 232, "name": "富有", "rarity": "rare", "description": "累计抽奖25次", "unlock_type": "condition"},
    233: {"id": 233, "name": "上瘾", "rarity": "rare", "description": "累计抽奖50次", "unlock_type": "condition"},
    234: {"id": 234, "name": "戒戒你好", "rarity": "legendary", "description": "累计抽奖100次", "unlock_type": "condition"},
    235: {"id": 235, "name": "大赚", "rarity": "rare", "description": "抽到10点积分", "unlock_type": "condition"},
    236: {"id": 236, "name": "BUG", "rarity": "legendary", "description": "连续3次什么都没抽到", "unlock_type": "condition"},
}



def get_title_def(title_id):
    return TITLE_DEFS.get(title_id)


def get_lottery_title_ids():
    return [tid for tid, data in TITLE_DEFS.items() if data.get("unlock_type") == "lottery"]


def evaluate_and_unlock_titles(dbmanager, user_id, checkin_dt: datetime | None = None):
    user_id = int(user_id)
    newly_unlocked = []

    def unlock(tid):
        if tid in TITLE_DEFS and not dbmanager.has_title(user_id, tid):
            dbmanager.unlock_title(user_id, tid)
            newly_unlocked.append(tid)

    if checkin_dt is not None:
        h, m = checkin_dt.hour, checkin_dt.minute
        # 时段
        if (h > 8 or (h == 8 and m >= 0)) and h < 12:
            unlock(201)
        if (h > 14 or (h == 14 and m >= 0)) and h < 16:
            unlock(202)
        if (h > 17 or (h == 17 and m >= 30)) and (h < 18 or (h == 18 and m <= 30)):
            unlock(203)
        if (h > 1 or (h == 1 and m >= 0)) and h < 5:
            unlock(204)
        weekday = checkin_dt.weekday()  # mon=0
        if (weekday == 6 and (h > 23 or (h == 23 and m >= 30))) or (weekday == 0 and h < 8):
            unlock(205)

        # 日期
        mmdd = (checkin_dt.month, checkin_dt.day)
        mapping = {
            (5, 1): 212,
            (4, 1): 213,
            (6, 1): 214,
            (10, 24): 215,
            (2, 22): 216,
            (2, 14): 217,
            (8, 11): 218,
            (3, 14): 219,
            (1, 1): 221,
        }
        if mmdd in mapping:
            unlock(mapping[mmdd])
        if checkin_dt.month == checkin_dt.day:
            unlock(220)
        if (h == 23 and m == 59) or (h == 0 and m in (0, 1)):
            unlock(210)
        if h == 0 and m == 0:
            unlock(211)

    # 累计打卡天数
    total_days = dbmanager.get_total_distinct_checkin_days(user_id)
    if total_days >= 30:
        unlock(209)
    if total_days >= 100:
        unlock(208)
    if total_days >= 200:
        unlock(207)
    if total_days >= 365:
        unlock(206)

    # 抽奖画像（兼容旧数据：draw_count 至少为 total_spent）
    profile = dbmanager.get_user_lottery_profile(user_id)
    spent = dbmanager.get_lottery_spent(user_id)
    draw_count = max(profile["draw_count"], spent)
    if draw_count >= 1:
        unlock(230)
    if draw_count >= 10:
        unlock(231)
    if draw_count >= 25:
        unlock(232)
    if draw_count >= 50:
        unlock(233)
    if draw_count >= 100:
        unlock(234)
    if profile["duplicate_count"] >= 1:
        unlock(227)
    if profile["duplicate_count"] >= 10:
        unlock(228)
    if profile["duplicate_count"] >= 100:
        unlock(229)
    if profile["has_hit_ten"] >= 1:
        unlock(235)
    if profile["max_zero_streak"] >= 3:
        unlock(236)

    # 依赖称号状态的进度称号
    titles = dbmanager.get_user_titles(user_id)
    cnt = len(titles)
    if cnt >= 10:
        unlock(222)
    if cnt >= 20:
        unlock(223)
    if cnt >= 30:
        unlock(224)

    titles = dbmanager.get_user_titles(user_id)
    if any((TITLE_DEFS.get(t, {}).get("rarity") == "legendary") for t in titles):
        unlock(225)

    equipped = dbmanager.get_equipped_titles(user_id)
    if len(equipped) == 3 and all((TITLE_DEFS.get(t, {}).get("rarity") == "legendary") for t in equipped):
        unlock(226)

    return newly_unlocked


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

    def _send_unlocked_titles_notice(self, user_id, unlocked_ids):
        if not unlocked_ids:
            return
        lines = ["解锁新称号："]
        for tid in unlocked_ids:
            data = TITLE_DEFS.get(tid, {"name": "未知称号", "rarity": "unknown"})
            lines.append(f"[{tid}] 「{data['name']}」 ({data['rarity']})")
        self.api.send_msg(at(user_id), text("\n".join(lines)))

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
        unlocked = evaluate_and_unlock_titles(self.dbmanager, user_id)
        self._send_unlocked_titles_notice(user_id, unlocked)
        self.api.send_msg(at(user_id), text(f"已装备称号：「{data['name']}」"))

    def _unequip(self, user_id):
        self.dbmanager.clear_equipped_titles(user_id)
        unlocked = evaluate_and_unlock_titles(self.dbmanager, user_id)
        self._send_unlocked_titles_notice(user_id, unlocked)
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
        unlocked = evaluate_and_unlock_titles(self.dbmanager, user_id)
        self._send_unlocked_titles_notice(user_id, unlocked)
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
