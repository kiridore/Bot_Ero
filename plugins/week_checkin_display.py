from core.base import Plugin
from core.cq import text,at,image
from core.utils import get_monday_to_monday

from core.utils import register_plugin
@register_plugin
class WeekCheckinDisplayPlugin(Plugin):
    name = 'show_week_checkin_images'
    description = '展示用户本周打卡图片。'

    def match(self, message_type):
        return self.on_full_match_any("/本周打卡图", "/本週打卡圖")

    def handle(self):
        if self.bot_event.user_id == None:
            return

        start_date, end_date = get_monday_to_monday()
        rows = self.dbmanager.search_target_user_checkin_range(self.bot_event.user_id, start_date, end_date)
        time_map = {}
        for row in rows:
            time_map.setdefault(row[2], 0)
            time_map[row[2]] += 1
        
        self.api.send_msg(
            at(self.bot_event.user_id),
            text(
                "\n本周一共打了{}次卡\n收录了{}张图".format(
                    len(time_map),
                    len(rows)
                )
            )
        )
        for row in rows:
            image_file = self.api.get_image(row[3])
            self.api.send_private_msg(image(image_file))
