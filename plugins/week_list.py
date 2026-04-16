from core.base import Plugin
from core.cq import text
from core.utils import get_monday_to_monday
from core.logger import logger
from plugins.title import get_title_def

# 每周打卡板油
class WeekListPlugin(Plugin):
    name = 'show_weekly_checkin_members'
    description = '展示本周完成打卡的成员列表。'

    def _format_title_prefix(self, user_id):
        titles = self.dbmanager.get_equipped_titles(user_id)[:3]
        if len(titles) == 0:
            return ""
        names = []
        for tid in titles:
            data = get_title_def(tid)
            if data and data.get("name"):
                names.append(data["name"])
        if len(names) == 0:
            return ""
        return "「{}」".format("·".join(names))

    def match(self, message_type):
        return self.on_full_match("/本周板油")

    def handle(self):
        #计算本周起止日期
        start_date, end_date = get_monday_to_monday()
        checkin_users = self.dbmanager.search_all_user_checkin_range(start_date, end_date)
        if len(checkin_users) <= 0:
            self.api.send_msg(text("本周({}-{})竟然还没有板油完成打卡".format(start_date, end_date)))
        else:
            display_str = ""
            user_map = {}
            logger.debug(checkin_users)
            #[(1, 1057613133, '2025-08-12 01:22:56', 'EDE6A7B4C56C0F2180D1C54AF7877B0C.png')]
            for user_info in checkin_users:
                user_map[user_info[1]] = user_info[2]

            for user_id, checkin_time in user_map.items():
                group_member_info = self.api.get_group_member_info(user_id)
                member_name = group_member_info["card"] 
                if group_member_info["card"] == "":
                    member_name = group_member_info["nickname"]
                title_prefix = self._format_title_prefix(user_id)
                if title_prefix:
                    member_name = f"{title_prefix}{member_name}"

                display_row = "- {}, {}\n".format(member_name, checkin_time)
                display_str += display_row
            final_str = """本周({}-{})
- 共有{}名板油完成了打卡:
{}"""
            self.api.send_msg(text(final_str.format(start_date, end_date, len(user_map), display_str)))
