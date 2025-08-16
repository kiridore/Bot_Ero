from core.base import Plugin
from core.cq import text,image
from core.utils import get_week_start_end
from core.logger import logger

class RollbackCheckinPlugin(Plugin):
    def match(self):
        return self.on_full_match("/撤回打卡")

    def handle(self):
        start_date, end_date = get_week_start_end()
        rows = self.search_target_user_checkin_range(self.context["user_id"], start_date + " 00:00:00", end_date + " 23:59:59")
        if len(rows) <= 0:
            self.send_msg(text("本周你还没打过卡呢！"))
        else:
            del_image = self.get_image(rows[0][3])
            del_time = rows[0][2]
            logger.debug(rows)
            self.send_msg(text("成功撤回了本周最近一次打卡喵:\n{}".format(del_time)), image(del_image))
            self.delete_checkin_by_id(rows[0][0])
