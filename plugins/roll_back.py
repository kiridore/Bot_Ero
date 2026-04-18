from core import utils
from core.base import Plugin
from core.cq import text,image
from core.utils import get_monday_to_monday
from core.logger import logger
from datetime import datetime, timedelta

from core.utils import register_plugin
@register_plugin
class RollbackCheckinPlugin(Plugin):
    name = 'rollback_checkin'
    description = '撤回用户本周最近一次打卡并回滚奖励。'

    def _rollback_attendance_rewards(self, user_id, dt):
        # 自然周奖励回滚
        week_start = dt.date() - timedelta(days=dt.weekday())
        week_end = week_start + timedelta(days=7)
        week_days = self.dbmanager.get_distinct_checkin_day_count(
            user_id,
            week_start.strftime("%Y-%m-%d 00:00:00"),
            week_end.strftime("%Y-%m-%d 00:00:00"),
        )
        if week_days < 7:
            points = self.dbmanager.revoke_attendance_rewards_by_type_and_range(
                user_id,
                "full_week_daily",
                week_start.strftime("%Y-%m-%d"),
                week_end.strftime("%Y-%m-%d"),
            )
            if points > 0:
                utils.add_user_point(self.dbmanager, user_id, -points)

        # 自然月奖励回滚
        month_start = dt.replace(day=1)
        if month_start.month == 12:
            next_month_start = month_start.replace(year=month_start.year + 1, month=1, day=1)
        else:
            next_month_start = month_start.replace(month=month_start.month + 1, day=1)
        month_key = month_start.strftime("%Y-%m")
        month_days = (next_month_start - month_start).days
        cur_days = self.dbmanager.get_distinct_checkin_day_count(
            user_id,
            month_start.strftime("%Y-%m-%d 00:00:00"),
            next_month_start.strftime("%Y-%m-%d 00:00:00"),
        )
        if cur_days < month_days:
            points = self.dbmanager.revoke_attendance_rewards_by_type_and_prefix(
                user_id,
                "full_month_weekly_check",
                month_key,
            )
            if points > 0:
                utils.add_user_point(self.dbmanager, user_id, -points)

    def match(self, message_type):
        return self.on_full_match("/撤回打卡")

    def handle(self):
        if self.bot_event.user_id == None:
            return

        start_date, end_date = get_monday_to_monday()
        rows = self.dbmanager.search_target_user_checkin_range(self.bot_event.user_id, start_date, end_date)
        if len(rows) <= 0:
            self.api.send_msg(text("本周你还没打过卡呢！"))
        else:
            del_image = self.api.get_image(rows[0][3])
            del_time = rows[0][2]
            logger.debug(rows)
            self.api.send_msg(text("成功撤回了本周最近一次打卡喵:\n{}".format(del_time)), image(del_image))

            if len(rows) == 1:
                self.api.send_msg(text("你刚刚撤回了本周第一次打卡，需要扣掉本周的点数喵！"))
                utils.add_user_point(self.dbmanager, self.bot_event.user_id, -1)
                week_start = start_date.split(" ")[0]
                month_weekly_points = self.dbmanager.revoke_attendance_reward_if_claimed(
                    self.bot_event.user_id, "full_month_weekly_check", week_start
                )
                if month_weekly_points > 0:
                    utils.add_user_point(self.dbmanager, self.bot_event.user_id, -month_weekly_points)

            self.dbmanager.delete_checkin_by_id(rows[0][0])
            dt = datetime.strptime(del_time, "%Y-%m-%d %H:%M:%S")
            self._rollback_attendance_rewards(self.bot_event.user_id, dt)
