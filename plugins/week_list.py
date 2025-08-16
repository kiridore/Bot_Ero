from core.base import Plugin
from core.cq import text
from core.utils import get_week_start_end
from core.logger import logger

# 每周打卡板油
class WeekListPlugin(Plugin):
    def match(self):
        return self.on_full_match("/本周板油")

    def handle(self):
        #计算本周起止日期
        start_date, end_date = get_week_start_end()
        checkin_users = self.search_all_user_checkin_range(start_date + " 00:00:00", end_date + " 23:59:59")
        if len(checkin_users) <= 0:
            self.send_msg(text("本周({}-{})竟然还没有板油完成打卡".format(start_date, end_date)))
        else:
            display_str = ""
            user_map = {}
            logger.debug(checkin_users)
            #[(1, 1057613133, '2025-08-12 01:22:56', 'EDE6A7B4C56C0F2180D1C54AF7877B0C.png')]
            for user_info in checkin_users:
                user_map[user_info[1]] = user_info[2]

            for user_id, checkin_time in user_map.items():
                group_member_info = self.get_group_member_info(user_id)
                display_row = "{}, {}\n".format(group_member_info["card"], checkin_time)
                display_str += display_row
            self.send_msg(text("{}-{}\n共有{}名板油完成了打卡:\n{}".format(start_date, end_date, len(user_map), display_str)))
