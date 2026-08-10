import random
from core.base import CommandPlugin
from core.cq import text,at
from core.logger import logger
from core.utils import add_user_point, get_monday_to_monday, on_quest_trigger
from core.timeline_client import emit_event
from datetime import datetime
from plugins.title import evaluate_and_unlock_titles, get_title_def

from core.utils import register_plugin
# 打卡插件
@register_plugin
class CheckinPlugin(CommandPlugin):
    name = 'checkin'
    description = '记录用户本周打卡图片并结算奖励。'
    COMMANDS = "/打卡"

    def handle(self):
        if self.bot_event.user_id == None:
            return

        img_list = []
        for message_unit in self.bot_event.message:
            if message_unit['type'] == 'image':
                img_list.append(message_unit['data']['file'])
        if len(img_list) <= 0:
            self.api.send_msg(text("没有图片是没办法打卡的喵"))
        else:
            for img_name in img_list :
                # 找到的图片列表
                logger.debug("{}".format(self.api.get_image(img_name)))

            start_date, end_date = get_monday_to_monday()

            # 确定是否首次打卡
            before_checkin_list = self.dbmanager.checkin.search_user_range(self.bot_event.user_id, start_date, end_date)
            is_first = False
            if len(before_checkin_list) == 0:
                is_first = True

            # 先打卡（带上 message_id，便于撤回消息时撤销记录）
            msg_id = self.bot_event.message_id
            self.dbmanager.checkin.insert(self.bot_event.user_id, img_list, msg_id)
            checkin_luck_bonus = 0
            if self.dbmanager.shop.pop_luck(self.bot_event.user_id):
                if random.random() < 0.1:
                    checkin_luck_bonus = 1
            unlocked = evaluate_and_unlock_titles(self.dbmanager, self.bot_event.user_id, datetime.now())
            if unlocked:
                lines = ["解锁新称号："]
                for tid in unlocked:
                    data = get_title_def(tid) or {"name": "未知称号", "rarity": "unknown", "description": "无"}
                    lines.append(f"[{tid}] 「{data['name']}」 ({data['rarity']}) - {data['description']}")
                self.api.send_msg(at(self.bot_event.user_id), text("\n".join(lines)))

            # 后搜索
            checkin_list = self.dbmanager.checkin.search_user_range(self.bot_event.user_id, start_date, end_date)
            streak_res = self.dbmanager.checkin.streaks(self.bot_event.user_id)

            # 社区时间线事件（best-effort；dedup_key 按打卡日期，撤回/回滚按它删除）
            emit_event(
                source="checkin",
                actor_id=self.bot_event.user_id,
                actor_qq=self.bot_event.user_id,
                title="{id:%s} 完成打卡" % self.bot_event.user_id,
                description="本周第 %d 次" % len(checkin_list),
                data={"images": [
                    "/thumb/%s/%s" % (
                        self.bot_event.user_id,
                        img.replace("{", "").replace("}", "").replace("-", ""),
                    )
                    for img in img_list
                ]},
                dedup_key="checkin:%s:%s" % (
                    self.bot_event.user_id,
                    datetime.now().strftime("%Y-%m-%d"),
                ),
            )

            display_str = "\n🌟打卡成功喵🌟\n收录了{}张图片\n".format(len(img_list))

            if is_first:
                display_str += "完成本周首次打卡喵~"
            else:
                display_str += "这周已经提交了{}张图了喵".format(len(checkin_list))

            bonus_total = 0
            bonus_lines = []
            week_start = start_date.split(" ")[0]

            now_dt = datetime.now()

            # 自然月全勤奖励（每自然月一次）
            month_start = now_dt.replace(day=1)
            if month_start.month == 12:
                next_month_start = month_start.replace(year=month_start.year + 1, month=1, day=1)
            else:
                next_month_start = month_start.replace(month=month_start.month + 1, day=1)
            month_full_days = self.dbmanager.checkin.count_days(
                self.bot_event.user_id,
                month_start.strftime("%Y-%m-%d 00:00:00"),
                next_month_start.strftime("%Y-%m-%d 00:00:00"),
            )
            month_days = (next_month_start - month_start).days
            if is_first and month_full_days >= month_days and self.dbmanager.checkin.claim_attendance(
                self.bot_event.user_id, "full_month_weekly_check", week_start, 1
            ):
                bonus_total += 1
                bonus_lines.append("当月全勤奖励 +1")

            if checkin_luck_bonus:
                bonus_total += checkin_luck_bonus
                bonus_lines.append("打卡增强：概率奖励 +1")

            if bonus_total > 0:
                add_user_point(self.dbmanager, self.bot_event.user_id, bonus_total)
                display_str += "\n" + "\n".join(bonus_lines)

            completed = on_quest_trigger(self.dbmanager, self.bot_event.user_id, "checkin")
            if completed:
                names = [f"{q['name']} +{q['reward']}" for q in completed]
                display_str += "\n🎯 " + " | ".join(names)

            if streak_res["current_weekly"] > 1:
                display_str += "\n已经连续打卡了{}周了，真厉害喵！".format(streak_res["current_weekly"])

            self.api.send_msg(at(self.bot_event.user_id), text(display_str))
