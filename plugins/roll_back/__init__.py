from datetime import datetime

from core.base import CommandPlugin
from core.cq import text, image
from core.utils import get_monday_to_monday, register_plugin
from core.timeline_client import retract_event
from core.logger import logger


@register_plugin
class RollbackCheckinPlugin(CommandPlugin):
    name = 'rollback_checkin'
    description = '撤回用户本周最近一次打卡并回滚奖励。'
    COMMANDS = "/撤回打卡"

    def handle(self):
        if self.bot_event.user_id is None:
            return
        start_date, end_date = get_monday_to_monday()
        rows = self.dbmanager.checkin.search_user_range(self.bot_event.user_id, start_date, end_date)
        if not rows:
            self.submit_message(text("本周你还没打过卡呢！"))
            return
        del_image = self.api.get_image(rows[0][3])
        del_time = rows[0][2]
        logger.debug(rows)
        self.submit_message(text("成功撤回了本周最近一次打卡喵:\n{}".format(del_time)), image(del_image))
        dt = datetime.strptime(del_time, "%Y-%m-%d %H:%M:%S")
        self.dbmanager.checkin.delete(rows[0][0])
        retract_event(
            "checkin",
            dedup_key="checkin:%s:%s:%s" % (self.bot_event.user_id, dt.strftime("%Y-%m-%d"), rows[0][4]),
        )
        self.publish_event("checkin.retracted", removed_at=dt.isoformat())
