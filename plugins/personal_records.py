from datetime import datetime
import os
from core import context
from core.base import Plugin
from core.cq import image, text,at
import core.utils as utils
import core.gen_image as gen_image

class PersonalRecords(Plugin):
    def match(self, message_type):
        return self.on_command("/档案") 

    def handle(self):
        # TODO@支持At某人查看他的档案
        year = int(datetime.today().year)
        if len(self.args) > 1:
            year = int(self.args[1])

        rows = self.dbmanager.search_checkin_year(self.context["user_id"], year)
        time_map = {}
        day_checkin_count = [0] * 366 # 全年每一天打卡数记录
        for row in rows:
            if row[3] != "remedy_checkin":
                time_map.setdefault(row[2], 0)
                time_map[row[2]] += 1
                day_checkin_count[utils.day_of_year(row[2]) - 1] += 1
            else:
                day_checkin_count[utils.day_of_year(row[2]) - 1] = -1
        
        display_str = "打卡记录\n"
        display_str = display_str + ("总次数({}): {}\n".format(year, len(time_map)))
        display_str = display_str + ("打卡图({}): {}张\n".format(year, len(rows)))

        display_str = display_str + ("------\n")

        streak_res = self.dbmanager.get_user_streaks(self.context["user_id"])

        display_str = display_str + ("当前连续（周）: {}\n".format(streak_res["current_weekly"]))
        display_str = display_str + ("最长连击（周）: {}\n".format(streak_res["longest_weekly"]))

        display_str = display_str + ("当前连续（日）: {}\n".format(streak_res["current_daily"]))
        display_str = display_str + ("最长连续（日）: {}\n".format(streak_res["longest_daily"]))

        display_str = display_str + ("点数: {}\n".format(self.dbmanager.get_user_point(self.context['user_id'])))
        
        gen_image.gen_year_heatmap(year, day_checkin_count, self.context["user_id"])
        image_path = os.path.abspath("{}/personal_records/{}_calendar_heatmap_monthly.png".format(context.llonebot_data_path, self.context["user_id"]))
        self.api.send_msg(at(self.context["user_id"]), text(display_str), image("file://" + image_path))
