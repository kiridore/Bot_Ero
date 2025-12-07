from core.base import Plugin
from core.cq import text,image
from core.utils import get_monday_to_monday
from core.logger import logger

class RollbackCheckinPlugin(Plugin):
    def match(self):
        return self.on_full_match("/撤回打卡")

    def handle(self):
        start_date, end_date = get_monday_to_monday()
        rows = self.dbmanager.search_target_user_checkin_range(self.context["user_id"], start_date, end_date)
        if len(rows) <= 0:
            self.send_msg(text("本周你还没打过卡呢！"))
        else:
            del_image = self.get_image(rows[0][3])
            del_time = rows[0][2]
            logger.debug(rows)
            self.send_msg(text("成功撤回了本周最近一次打卡喵:\n{}".format(del_time)), image(del_image))
            self.dbmanager.delete_checkin_by_id(rows[0][0])
