from datetime import datetime, timedelta

import requests

from core.base import TimedHeartbeatPlugin
from core.cq import image, text
from core.utils import register_plugin

_NEWS_LIST_URL = "https://cqnews.web.sdo.com/api/news/newsList"
_NEWS_LIST_BASE_PARAMS = {
    "gameCode": "ff",
    "CategoryCode": "8324,8325,8326,8327,5309,5310,5311,5312,5313",
    "pageIndex": "0",
}
_NEWS_CONT_BASE = "https://ff.web.sdo.com/web8/index.html#/newstab/newscont/"


def _parse_publish_date(raw: str) -> datetime | None:
    s = (raw or "").strip()
    if not s:
        return None
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


@register_plugin
class FfNewsPlugin(TimedHeartbeatPlugin):
    name = "ff_news"
    description = "拉取最终幻想14国服官网近期新闻标题与链接；整点检测最新一条并在发布后1小时内推送群聊。"

    def should_run_on_heartbeat(self, event_type: str) -> bool:
        if event_type != "meta":
            return False
        now = datetime.now()
        if now.minute != 0:
            return False
        if not self._passes_weekday_filter(now):
            return False
        if not self._passes_annual_filter(now):
            return False
        run_key = now.strftime("%Y-%m-%d %H:%M")
        plugin_name = type(self).__name__
        if TimedHeartbeatPlugin._last_run_minute.get(plugin_name) == run_key:
            return False
        TimedHeartbeatPlugin._last_run_minute[plugin_name] = run_key
        return True

    def match(self, message_type):
        return self.should_run_on_heartbeat(message_type) or self.on_command_any("/FF新闻")

    def _fetch_payload(self, page_size: int):
        params = {**_NEWS_LIST_BASE_PARAMS, "pageSize": str(page_size)}
        r = requests.get(_NEWS_LIST_URL, params=params, timeout=25)
        r.raise_for_status()
        return r.json()

    def _handle_manual(self):
        try:
            payload = self._fetch_payload(5)
        except Exception:
            self.api.send_msg(text("获取新闻失败，请稍后再试。"))
            return

        if str(payload.get("Code")) != "0":
            self.api.send_msg(text("新闻接口返回异常，请稍后再试。"))
            return

        items = payload.get("Data") or []
        if not items:
            self.api.send_msg(text("暂无新闻。"))
            return

        lines = ["FF14 官方新闻（最近5条）"]
        for i, row in enumerate(items, 1):
            title = (row.get("Title") or "").strip() or "(无标题)"
            nid = row.get("Id")
            link = f"{_NEWS_CONT_BASE}{nid}"
            lines.append(f"{i}. {title}")
            lines.append(link)

        self.api.send_msg(text("\n".join(lines)))

    def _handle_hourly(self):
        try:
            payload = self._fetch_payload(1)
        except Exception:
            return

        if str(payload.get("Code")) != "0":
            return

        items = payload.get("Data") or []
        if not items:
            return

        row = items[0]
        pub = _parse_publish_date(row.get("PublishDate") or "")
        if pub is None:
            return
        now = datetime.now()
        if pub > now or now - pub > timedelta(hours=1):
            return

        title = (row.get("Title") or "").strip() or "(无标题)"
        summary = (row.get("Summary") or "").strip()
        nid = row.get("Id")
        link = f"{_NEWS_CONT_BASE}{nid}"

        body = f"【FF14 官网快讯】\n{title}\n{summary}\n{link}".strip()
        img_url = (row.get("HomeImagePath") or "").strip()

        if img_url:
            self.api.send_msg(text(body), image(img_url))
        else:
            self.api.send_msg(text(body))

    def handle(self):
        if self.bot_event.post_type == "meta_event":
            self._handle_hourly()
        else:
            self._handle_manual()
