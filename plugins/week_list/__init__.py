from core.base import CommandPlugin
from core.cq import image, text
from core.utils import get_monday_to_monday
from core.logger import logger
from core.gen_image import RankRow, fetch_avatar_cached, render_rank_card, save_rank_png
from plugins.title import get_title_def

from core.utils import register_plugin
# 每周打卡板油
@register_plugin
class WeekListPlugin(CommandPlugin):
    name = 'show_weekly_checkin_members'
    description = '展示本周完成打卡的成员列表。'
    COMMANDS = ("/本周板油", "/本週板油")

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
        #计算本周起止日期
        start_date, end_date = get_monday_to_monday()
        checkin_users = self.dbmanager.checkin.search_range(start_date, end_date)
        if len(checkin_users) <= 0:
            self.api.send_msg(text("本周({}-{})竟然还没有板油完成打卡".format(start_date, end_date)))
            return

        user_map = {}
        logger.debug(checkin_users)
        #[(1, 123456, '2025-08-12 01:22:56', 'EDE6A7B4C56C0F2180D1C54AF7877B0C.png')]
        for user_info in checkin_users:
            user_map[user_info[1]] = user_info[2]

        entries = []  # (序号, user_id, 展示名, 打卡时间)
        for user_id, checkin_time in user_map.items():
            member_name = str(user_id)
            try:
                info = self.api.get_group_member_info(user_id)
                member_name = info.get("card") or info.get("nickname") or str(user_id)
            except Exception:
                member_name = str(user_id)
            title_prefix = self._format_title_prefix(user_id)
            if title_prefix:
                member_name = f"{title_prefix}{member_name}"
            entries.append((len(entries) + 1, user_id, member_name, checkin_time))

        try:
            rows = [
                RankRow(
                    rank=rank,
                    name=name,
                    detail=str(checkin_time),
                    avatar=fetch_avatar_cached(self.api, int(user_id)),
                )
                for rank, user_id, name, checkin_time in entries
            ]
            subtitle = "本周({} ~ {}) 共 {} 名板油完成了打卡".format(start_date, end_date, len(entries))
            img = render_rank_card("本周打卡板油", subtitle, rows)
            _, send_path = save_rank_png("week_board", img)
            self.api.send_msg(image("file://" + send_path))
        except Exception:
            logger.exception("本周板油图片生成失败，回退纯文本")
            display_str = "".join("- {}, {}\n".format(name, checkin_time)
                                  for _, _, name, checkin_time in entries)
            self.api.send_msg(text(
                "本周({}-{})\n- 共有{}名板油完成了打卡:\n{}".format(
                    start_date, end_date, len(entries), display_str)
            ))
