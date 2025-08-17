from core.base import Plugin
from core.cq import text,at

class PersonalRecords(Plugin):
    def match(self):
        return self.on_full_match("/个人打卡记录") or self.on_full_match("/档案") 

    def handle(self):
        # TODO@支持At某人查看他的档案
        rows = self.search_checkin_all(self.context["user_id"])
        time_map = {}
        for row in rows:
            time_map.setdefault(row[2], 0)
            time_map[row[2]] += 1
        total_str = "总次数: {}\n".format(len(time_map))
        image_count_str = "打卡图: {}张\n".format(len(rows))
        nearest_checkin_str = "最近打卡: {}\n".format(next(iter(time_map)))
        display_str = "的打卡记录\n" + total_str + image_count_str + nearest_checkin_str

        self.send_msg(at(self.context["user_id"]), text(display_str))
