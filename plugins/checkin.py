from core.base import Plugin
from core.cq import text,at
from core.logger import logger
from core.utils import add_user_point, get_monday_to_monday
from datetime import datetime, timedelta
from plugins.title import evaluate_and_unlock_titles, get_title_def

# 打卡插件
class CheckinPlugin(Plugin):
    def match(self, message_type):
        return self.on_begin_with("/打卡")

    def handle(self):
        img_list = []
        for message_unit in self.context["message"]:
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
            before_checkin_list = self.dbmanager.search_target_user_checkin_range(self.context["user_id"], start_date, end_date)
            is_first = False
            if len(before_checkin_list) == 0:
                is_first = True

            # 先打卡（带上 message_id，便于撤回消息时撤销记录）
            msg_id = self.context.get("message_id")
            self.dbmanager.insert_checkin(self.context["user_id"], img_list, msg_id)
            unlocked = evaluate_and_unlock_titles(self.dbmanager, self.context["user_id"], datetime.now())
            if unlocked:
                lines = ["解锁新称号："]
                for tid in unlocked:
                    data = get_title_def(tid) or {"name": "未知称号", "rarity": "unknown"}
                    lines.append(f"[{tid}] 「{data['name']}」 ({data['rarity']})")
                self.api.send_msg(at(self.context["user_id"]), text("\n".join(lines)))

            # 后搜索
            checkin_list = self.dbmanager.search_target_user_checkin_range(self.context["user_id"], start_date, end_date)
            streak_res = self.dbmanager.get_user_streaks(self.context["user_id"])

            display_str = "\n🌟打卡成功喵🌟\n收录了{}张图片\n".format(len(img_list))

            if is_first:
                display_str += "完成本周首次打卡喵~"
            else:
                display_str += "这周已经提交了{}张图了喵".format(len(checkin_list))

            bonus_total = 0
            bonus_lines = []
            week_start = start_date.split(" ")[0]

            now_dt = datetime.now()
            # 自然周全勤奖励（每自然周一次）
            natural_week_start = now_dt - timedelta(days=now_dt.weekday())
            natural_week_end = natural_week_start + timedelta(days=7)
            week_start_str = natural_week_start.strftime("%Y-%m-%d")
            week_end_str = natural_week_end.strftime("%Y-%m-%d")
            week_full_days = self.dbmanager.get_distinct_checkin_day_count(
                self.context["user_id"],
                f"{week_start_str} 00:00:00",
                f"{week_end_str} 00:00:00",
            )
            if week_full_days >= 7 and self.dbmanager.claim_attendance_reward(
                self.context["user_id"], "full_week_daily", now_dt.strftime("%Y-%m-%d"), 1
            ):
                bonus_total += 1
                bonus_lines.append("自然周全勤奖励 +1")

            # 自然月全勤奖励（每自然月一次）
            month_start = now_dt.replace(day=1)
            if month_start.month == 12:
                next_month_start = month_start.replace(year=month_start.year + 1, month=1, day=1)
            else:
                next_month_start = month_start.replace(month=month_start.month + 1, day=1)
            month_full_days = self.dbmanager.get_distinct_checkin_day_count(
                self.context["user_id"],
                month_start.strftime("%Y-%m-%d 00:00:00"),
                next_month_start.strftime("%Y-%m-%d 00:00:00"),
            )
            month_days = (next_month_start - month_start).days
            if is_first and month_full_days >= month_days and self.dbmanager.claim_attendance_reward(
                self.context["user_id"], "full_month_weekly_check", week_start, 1
            ):
                bonus_total += 1
                bonus_lines.append("当月全勤奖励 +1")

            if is_first:
                bonus_total += 1
                bonus_lines.append("当周首次打卡奖励 +1")

            if bonus_total > 0:
                add_user_point(self.dbmanager, self.context['user_id'], bonus_total)
                display_str += "\n" + "\n".join(bonus_lines)

            if streak_res["current_weekly"] > 1:
                display_str += "\n已经连续打卡了{}周了，真厉害喵！".format(streak_res["current_weekly"])

            self.api.send_msg(at(self.context["user_id"]), text(display_str))
