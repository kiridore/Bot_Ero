from core.base import Plugin
from core.cq import text

class HistoryPlugin(Plugin):
    def match(self):
        return self.on_full_match("/历史数据")

    def handle(self):
        group_id = self.context.get("group_id")
        if group_id != None:
            album_list = self.get_group_album_list(self.context["group_id"])
            print(album_list)
        else:
            self.send_msg(text("这个指令不能在私聊使用"))
