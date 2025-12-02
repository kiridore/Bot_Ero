import os
from core import context
from core.base import Plugin
from core.cq import image, text,at
from core.logger import logger
import core.utils as utils
import core.gen_image as gen_image

class PersonalRecords(Plugin):
    def match(self):
        return self.on_full_match("/个人打卡记录") or self.on_full_match("/档案") 

    def handle(self):
        # TODO@支持At某人查看他的档案
        rows = self.dbmanager.search_checkin_all(self.context["user_id"])
        time_map = {}
        day_checkin_count = [0] * 366 # 全年每一天打卡数记录
        for row in rows:
            time_map.setdefault(row[2], 0)
            time_map[row[2]] += 1
            day_checkin_count[utils.day_of_year(row[2])] += 1
        total_str = "总次数: {}\n".format(len(time_map))
        image_count_str = "打卡图: {}张\n".format(len(rows))
        nearest_checkin_str = "最近打卡: {}\n".format(next(iter(time_map)))
        display_str = "打卡记录\n" + total_str + image_count_str + nearest_checkin_str

        gen_image.gen_year_heatmap(2025, day_checkin_count, self.context["user_id"])
        image_path = os.path.abspath("{}/personal_records/{}_calendar_heatmap_monthly.png".format(context.llonebot_data_path, self.context["user_id"]))
        self.send_msg(at(self.context["user_id"]), text(display_str), image("file://" + image_path))
