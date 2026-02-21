from core import utils
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
            self.api.send_msg(text("本周你还没打过卡呢！"))
        else:
            del_image = self.api.get_image(rows[0][3])
            del_time = rows[0][2]
            logger.debug(rows)
            self.api.send_msg(text("成功撤回了本周最近一次打卡喵:\n{}".format(del_time)), image(del_image))

            if len(rows) == 1:
                self.api.send_msg(text("你刚刚撤回了本周第一次打卡，需要扣掉本周的点数喵！"))
                utils.add_user_point(self.dbmanager, self.context['user_id'], -1)

            self.dbmanager.delete_checkin_by_id(rows[0][0])
