from core.base import Plugin
from core.cq import text
from plugins.title import get_title_def


class LeaderboardPlugin(Plugin):
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
            title_prefix = self._format_title_prefix(user_id)
            if title_prefix:
                member_name = f"{title_prefix}{member_name}"
            lines.append(f"{index}. {member_name} - {points}分")

        content = "积分排行榜 TOP10\n" + "\n".join(lines)
        self.api.send_msg(text(content))
