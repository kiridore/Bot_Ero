from core.base import Plugin
from core.cq import text,at,image
from core.utils import get_monday_to_monday

class AllCheckinDisplay(Plugin):
    def match(self):
        return self.on_full_match("/ALL")

    def handle(self):
        rows = self.dbmanager.search_checkin_all(self.context["user_id"])
        time_map = {}
        for row in rows:
            time_map.setdefault(row[2], 0)
            time_map[row[2]] += 1
        
        self.send_msg(at(self.context["user_id"]), text("\n至今一共打了{}次卡\n收录了{}张图\n具体的图在这里……*翻找*".format(len(time_map), len(rows))))
        messages = []
        for row in rows:
            image_file = self.get_image(row[3])
            messages.append(image(image_file))

        self.send_forward_msg(messages)
