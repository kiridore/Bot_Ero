from core.base import CommandPlugin
from core.cq import image, text
from core.logger import logger
from core.gen_image import RankRow, fetch_avatar_cached, render_rank_card, save_rank_png
from plugins.title import get_title_def


from core.utils import register_plugin
@register_plugin
class LeaderboardPlugin(CommandPlugin):
    name = 'show_leaderboard'
    description = '展示积分排行榜。'
    COMMANDS = ("/排名", "/rank")

    def _format_title_prefix(self, user_id):
        titles = self.dbmanager.titles.equipped_all(user_id)[:3]
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

    def handle(self):
        group_id = self.bot_event.group_id
        if not group_id:
            self.api.send_msg(text("请在群里使用 /排名 或 /rank"))
            return

        top_rows = self.dbmanager.points.leaderboard(limit=10)
        if len(top_rows) == 0:
            self.api.send_msg(text("当前还没有积分数据喵~"))
            return

        entries = []  # (排名, user_id, 展示名, 积分)
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
            entries.append((index, user_id, member_name, points))

        try:
            rows = [
                RankRow(
                    rank=rank,
                    name=name,
                    detail=f"{points}分",
                    avatar=fetch_avatar_cached(self.api, int(user_id)),
                )
                for rank, user_id, name, points in entries
            ]
            img = render_rank_card("积分排行榜", f"TOP {len(rows)}", rows)
            _, send_path = save_rank_png("points_rank", img)
            self.api.send_msg(image("file://" + send_path))
        except Exception:
            logger.exception("积分排行榜图片生成失败，回退纯文本")
            lines = [f"{rank}. {name} - {points}分" for rank, _, name, points in entries]
            self.api.send_msg(text("积分排行榜 TOP10\n" + "\n".join(lines)))
