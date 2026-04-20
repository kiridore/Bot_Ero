from datetime import datetime
from io import BytesIO
import os

import requests
from PIL import Image as PILImage

from core import context
from core.base import Plugin
from core.cq import image, at
from core.event import Event
import core.utils as utils
from core.gen_image import PersonalRecordStats, gen_personal_record_card

from core.utils import register_plugin


def _sender_display_name(ev: Event) -> str:
    s = ev.sender
    if isinstance(s, dict):
        card = (s.get("card") or "").strip()
        if card:
            return card
        nick = (s.get("nickname") or "").strip()
        if nick:
            return nick
    uid = ev.user_id
    return f"QQ{uid}" if uid is not None else "未知用户"


def _load_avatar_from_url(url: str) -> PILImage.Image | None:
    try:
        r = requests.get(url, timeout=25)
        r.raise_for_status()
        im = PILImage.open(BytesIO(r.content))
        return im
    except Exception:
        return None


@register_plugin
class PersonalRecords(Plugin):
    name = 'show_personal_records'
    description = '生成并展示用户年度打卡档案。'

    def match(self, message_type):
        return self.on_command_any("/档案", "/檔案")

    def handle(self):
        if self.bot_event.user_id == None:
            return
        # TODO@支持At某人查看他的档案
        year = int(datetime.today().year)
        if len(self.args) > 1:
            year = int(self.args[1])

        rows = self.dbmanager.search_checkin_year(self.bot_event.user_id, year)
        time_map = {}
        day_checkin_count = [0] * 366  # 全年每一天打卡数记录
        for row in rows:
            if row[3] != "remedy_checkin":
                time_map.setdefault(row[2], 0)
                time_map[row[2]] += 1
                day_checkin_count[utils.day_of_year(row[2]) - 1] += 1
            else:
                day_checkin_count[utils.day_of_year(row[2]) - 1] = -1

        streak_res = self.dbmanager.get_user_streaks(self.bot_event.user_id)
        stats = PersonalRecordStats(
            year=year,
            total_distinct_days=len(time_map),
            total_checkin_images=len(rows),
            current_weekly=streak_res["current_weekly"],
            longest_weekly=streak_res["longest_weekly"],
            current_daily=streak_res["current_daily"],
            longest_daily=streak_res["longest_daily"],
            points=self.dbmanager.get_user_point(self.bot_event.user_id),
        )

        display_name = _sender_display_name(self.bot_event)
        avatar_im = None
        url = self.api.get_qq_avatar(self.bot_event.user_id)
        if url:
            avatar_im = _load_avatar_from_url(url)

        gen_personal_record_card(
            year,
            day_checkin_count,
            self.bot_event.user_id,
            stats,
            user_display_name=display_name,
            avatar=avatar_im,
        )
        image_path = os.path.abspath("{}/personal_records/{}_calendar_heatmap_monthly.png".format(
            context.llonebot_data_path,
            self.bot_event.user_id)
        )
        self.api.send_msg(at(self.bot_event.user_id), image("file://" + image_path))
