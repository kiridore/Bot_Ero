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
        display_str = "\n总打卡次数: {}次\n收录了{}张打卡图:\n".format(len(time_map), len(rows))
        for time_stamp, count in time_map.items():
            time_format_str = "{} {}张\n".format(time_stamp, count)
            display_str += time_format_str

        self.send_msg(at(self.context["user_id"]), text(display_str))
