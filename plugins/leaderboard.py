from core.base import Plugin
from core.cq import text


class LeaderboardPlugin(Plugin):
    def match(self, message_type):
        return self.on_full_match("/排名") or self.on_full_match("/rank")

    def handle(self):
        group_id = self.context.get("group_id")
        if not group_id:
            self.api.send_msg(text("请在群里使用 /排名 或 /rank"))
            return

        top_rows = self.dbmanager.get_point_leaderboard(limit=10)
        if len(top_rows) == 0:
            self.api.send_msg(text("当前还没有积分数据喵~"))
            return

        lines = []
        for index, (user_id, points) in enumerate(top_rows, start=1):
            member_name = str(user_id)
            try:
                member = self.api.get_group_member_info(int(user_id))
                member_name = member.get("card") or member.get("nickname") or str(user_id)
            except Exception:
                member_name = str(user_id)
            lines.append(f"{index}. {member_name} - {points}分")

        content = "积分排行榜 TOP10\n" + "\n".join(lines)
        self.api.send_msg(text(content))
