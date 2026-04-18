from core.base import Plugin
from core.cq import text,at,image

from core.utils import register_plugin
@register_plugin
class AllCheckinDisplay(Plugin):
    name = 'show_all_checkin_images'
    description = '展示用户历史全部打卡图片。'

    def match(self, message_type):
        return self.on_full_match("/ALL")

    def handle(self):
        if self.bot_event.user_id == None:
            return

        rows = self.dbmanager.search_checkin_all(self.bot_event.user_id)
        time_map = {}
        for row in rows:
            time_map.setdefault(row[2], 0)
            time_map[row[2]] += 1
        
        self.api.send_msg(at(self.bot_event.user_id), text("\n至今一共打了{}次卡\n收录了{}张图\n具体的图在这里……*翻找*".format(len(time_map), len(rows))))
        messages = []
        for row in rows:
            image_file = self.api.get_image(row[3])
            if image_file != "":
                messages.append(image(image_file))

        self.api.send_forward_msg(messages)
