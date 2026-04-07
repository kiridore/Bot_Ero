from datetime import datetime

from core.base import Plugin
from core.cq import text


class DailyMessageStatsPlugin(Plugin):
    def match(self, message_type):
        if message_type != "message":
            return False
        return self.context.get("post_type") == "message" and self.context.get("message_type") == "group"

    def handle(self):
        group_id = self.context.get("group_id")
        user_id = self.context.get("user_id")
        if not group_id or not user_id:
            return

        today = datetime.now().strftime("%Y-%m-%d")
        self.dbmanager.increment_group_daily_message_count(today, group_id, user_id, 1)

        if not self.on_full_match("/今日发言统计"):
            return

        rows = self.dbmanager.get_group_daily_message_stats(today, group_id, limit=20)
        if len(rows) == 0:
            self.api.send_msg(text("今天还没有任何发言记录喵~"))
            return

        lines = [f"今日发言统计（{today}）", "--------------------"]
        for idx, (uid, count) in enumerate(rows, start=1):
            member_name = str(uid)
            try:
                info = self.api.get_group_member_info(int(uid))
                member_name = info.get("card") or info.get("nickname") or str(uid)
            except Exception:
                member_name = str(uid)
            lines.append(f"{idx}. {member_name} - {count}条")

        self.api.send_msg(text("\n".join(lines)))
