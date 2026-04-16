from datetime import datetime, timedelta

from core import utils
from core.base import Plugin
from core.cq import at, text
from core.utils import get_monday_to_monday


from core.utils import register_plugin
@register_plugin
class CheckinRecallPlugin(Plugin):
    """群成员撤回自己的 /打卡 消息时，删除对应打卡记录（当周再无打卡时扣 1 点，与 /撤回打卡 一致）。"""

    name = 'auto_rollback_recalled_checkin'
    description = '在打卡消息被撤回时自动删除对应记录。'

    def match(self, event_type):
        if event_type != "notice":
            return False
        return self.context.get("notice_type") == "group_recall"

    def _rollback_attendance_rewards(self, user_id, dt):
        week_start = dt.date() - timedelta(days=dt.weekday())
        week_end = week_start + timedelta(days=7)
        week_key = week_start.strftime("%Y-%m-%d")
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

    def handle(self):
        user_id = self.context.get("user_id")
        raw_mid = self.context.get("message_id")
        if user_id is None or raw_mid is None:
            return
        try:
            message_id = int(raw_mid)
        except (TypeError, ValueError):
            return

        target_rows = self.dbmanager.get_checkins_by_message_id(user_id, message_id)
        if not target_rows:
            return

        checkin_date = target_rows[0][2]
        dt = datetime.strptime(checkin_date, "%Y-%m-%d %H:%M:%S")
        start_date, end_date = get_monday_to_monday(dt)

        week_before = self.dbmanager.search_target_user_checkin_range(
            user_id, start_date, end_date, limit=9999999
        )
        count_before_n = len(week_before)

        deleted = self.dbmanager.delete_checkin_by_message_id(user_id, message_id)
        if deleted <= 0:
            return

        week_after = self.dbmanager.search_target_user_checkin_range(
            user_id, start_date, end_date, limit=9999999
        )
        if len(week_after) == 0 and count_before_n > 0:
            utils.add_user_point(self.dbmanager, user_id, -1)
            week_start = start_date.split(" ")[0]
            month_weekly_points = self.dbmanager.revoke_attendance_reward_if_claimed(
                user_id, "full_month_weekly_check", week_start
            )
            if month_weekly_points > 0:
                utils.add_user_point(self.dbmanager, user_id, -month_weekly_points)
        self._rollback_attendance_rewards(user_id, dt)

        self.api.send_msg(
            at(user_id),
            text("已撤销你撤回的那条打卡消息对应的记录（含{}张图）".format(deleted)),
        )
