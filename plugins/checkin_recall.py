from datetime import datetime

from core import utils
from core.base import Plugin
from core.cq import at, text
from core.utils import get_monday_to_monday


class CheckinRecallPlugin(Plugin):
    """群成员撤回自己的 /打卡 消息时，删除对应打卡记录（当周再无打卡时扣 1 点，与 /撤回打卡 一致）。"""

    def match(self, event_type):
        if event_type != "notice":
            return False
        return self.context.get("notice_type") == "group_recall"

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

        self.api.send_msg(
            at(user_id),
            text("已撤销你撤回的那条打卡消息对应的记录（含{}张图）".format(deleted)),
        )
