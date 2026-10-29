from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable
from threading import Lock

import requests

from core.base import TimedHeartbeatPlugin
from core.cq import at, image, text
from core.logger import logger
from core.utils import register_plugin

_NEWS_LIST_URL = "https://cqnews.web.sdo.com/api/news/newsList"
_NEWS_LIST_BASE_PARAMS = {
    "gameCode": "ff",
    "CategoryCode": "8324,8325,8326,8327,5309,5310,5311,5312,5313",
    "pageIndex": "0",
}
_NEWS_CONT_BASE = "https://ff.web.sdo.com/web8/index.html#/newstab/newscont/"

# 推送间隔（分钟）：整点与半点各轮询一次
_POLL_MINUTES = (0, 30)
# 发布超过该时长的未见条目不推送（防长时间宕机后补推旧闻）
_MAX_AGE = timedelta(hours=48)


@dataclass(frozen=True)
class NewsItem:
    id: str  # 去重键，数值型字符串
    title: str
    summary: str
    link: str
    image_url: str
    published_at: datetime


@dataclass(frozen=True)
class NewsSource:
    key: str  # 稳定标识，入库做主键
    name: str  # 展示名
    push_header: str  # 推送正文首行，如【FF14 官网快讯】
    fetch: Callable[[], list[NewsItem]]  # 返回按新到旧排序的条目


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


def _fetch_ff14() -> list[NewsItem]:
    items = {}
    page, pages = 0, 1
    while page < pages:
        params = {**_NEWS_LIST_BASE_PARAMS, "pageSize": "50", "pageIndex": str(page)}
        r = requests.get(_NEWS_LIST_URL, params=params, timeout=25)
        r.raise_for_status()
        payload = r.json()
        if str(payload.get("Code")) != "0":
            raise ValueError("FF14 新闻接口返回异常")
        pages = int(payload.get("PageCount") or 1)
        if not 1 <= pages <= 200:
            raise ValueError("FF14 新闻接口页数超出预期")
        for row in payload.get("Data") or []:
            pub = _parse_publish_date(row.get("PublishDate") or "")
            nid = str(row.get("Id") or "")
            if pub is None or not nid.isascii() or not nid.isdigit():
                raise ValueError("FF14 新闻条目的编号或时间无效")
            items[int(nid)] = NewsItem(
                id=nid,
                title=(row.get("Title") or "").strip() or "(无标题)",
                summary=(row.get("Summary") or "").strip(),
                link=f"{_NEWS_CONT_BASE}{nid}",
                image_url=(row.get("HomeImagePath") or "").strip(),
                published_at=pub,
            )
        page += 1
    return [items[key] for key in sorted(items, reverse=True)]


# 消息源注册表：新增源 = 加一个 NewsSource 项；/订阅 编号即此列表序号（1 起）
_SOURCES: list[NewsSource] = [
    NewsSource(key="ff14", name="FF14 国服官网", push_header="【FF14 官网快讯】", fetch=_fetch_ff14),
]


@register_plugin
class NewsPlugin(TimedHeartbeatPlugin):
    _poll_lock = Lock()
    name = "news"
    description = "游戏新闻订阅：/订阅 查看与订阅消息源，有新消息时推送默认群并 @订阅者。"

    def should_run_on_heartbeat(self, event_type: str) -> bool:
        if event_type != "meta":
            return False
        now = datetime.now()
        if now.minute not in _POLL_MINUTES:
            return False
        run_key = now.strftime("%Y-%m-%d %H:%M")
        plugin_name = type(self).__name__
        if TimedHeartbeatPlugin._last_run_minute.get(plugin_name) == run_key:
            return False
        return True

    def match(self, message_type):
        return self.should_run_on_heartbeat(message_type) or (
            message_type == "message" and self.on_command_any("/订阅", "/退订")
        )

    # ---- 指令 ----

    def _source_by_arg(self) -> NewsSource | None | str:
        """解析编号参数：None = 无编号（列目录/用法提示），str = 编号非法，NewsSource = 命中。"""
        args = [a.strip() for a in self.args[1:] if a.strip()]
        if not args:
            return None
        if len(args) != 1:
            return "bad"
        try:
            idx = int(args[0])
        except ValueError:
            return "bad"
        if not 1 <= idx <= len(_SOURCES):
            return "bad"
        return _SOURCES[idx - 1]

    def _handle_subscribe(self, source: NewsSource | None, bad: bool):
        news = self.dbmanager.news
        if bad:
            self.api.send_msg(text("没有该编号的消息源，发送 /订阅 查看列表。"))
            return
        if source is None:
            lines = ["当前支持的消息源："]
            for i, s in enumerate(_SOURCES, 1):
                mark = "（已订阅）" if news.is_subscribed(self.bot_event.user_id, s.key) else "（未订阅）"
                lines.append(f"{i}. {s.name}{mark}")
            lines.append("订阅：/订阅 编号；退订：/退订 编号")
            self.api.send_msg(text("\n".join(lines)))
            return
        if news.is_subscribed(self.bot_event.user_id, source.key):
            self.api.send_msg(text(f"你已订阅「{source.name}」，无需重复订阅。"))
            return
        news.subscribe(self.bot_event.user_id, source.key)
        self.api.send_msg(text(f"已订阅「{source.name}」，该源有新消息时会提醒你。"))

    def _handle_unsubscribe(self, source: NewsSource | None, bad: bool):
        news = self.dbmanager.news
        if bad:
            self.api.send_msg(text("没有该编号的消息源，发送 /订阅 查看列表。"))
            return
        if source is None:
            self.api.send_msg(text("用法：/退订 消息源编号，发送 /订阅 查看列表。"))
            return
        if not news.is_subscribed(self.bot_event.user_id, source.key):
            self.api.send_msg(text(f"你尚未订阅「{source.name}」。"))
            return
        news.unsubscribe(self.bot_event.user_id, source.key)
        self.api.send_msg(text(f"已退订「{source.name}」。"))

    # ---- 轮询推送 ----

    def _poll_and_push(self):
        news = self.dbmanager.news
        for source in _SOURCES:
            try:
                items = source.fetch()
            except Exception:
                logger.exception("新闻源 %s 抓取失败，本轮跳过", source.key)
                continue
            if not items:
                continue
            try:
                cursor_val = int(news.get_cursor(source.key) or "")
            except ValueError:
                cursor_val = None  # 无游标（首次运行）
            max_id = max(int(it.id) for it in items)
            if cursor_val is None:
                # 首次运行只记位置不补推历史
                news.save_cursor(source.key, str(max_id))
                continue
            fresh = sorted({int(it.id): it for it in items if int(it.id) > cursor_val}.values(),
                           key=lambda it: int(it.id))
            subs = news.subscribers(source.key)
            now = datetime.now()
            for it in fresh:
                if it.published_at > now:
                    break  # 不提前推送，也不越过未来条目的游标
                if it.published_at >= now - _MAX_AGE and subs:
                    body = f"{source.push_header}\n{it.title}\n{it.summary}\n{it.link}".strip()
                    segs = [at(str(u)) for u in subs] + [text(body)]
                    if it.image_url:
                        segs.append(image(it.image_url))
                    try:
                        sent = self.api.send_msg(*segs)
                    except Exception:
                        logger.exception("新闻源 %s 发送失败", source.key)
                        break
                    if not sent:
                        logger.warning("新闻源 %s 发送未确认，保留游标", source.key)
                        break
                news.save_cursor(source.key, it.id)

    def handle(self):
        if self.bot_event.post_type == "meta_event":
            with self._poll_lock:
                if self.should_run_on_heartbeat("meta"):
                    TimedHeartbeatPlugin._last_run_minute[type(self).__name__] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    self._poll_and_push()
            return
        if not self.bot_event.is_group:
            self.api.send_msg(text("订阅指令仅限群聊使用，请在群内操作。"))
            return
        parsed = self._source_by_arg()
        source, bad = (None, parsed == "bad") if not isinstance(parsed, NewsSource) else (parsed, False)
        if self.args[0] == "/订阅":
            self._handle_subscribe(source, bad)
        else:
            self._handle_unsubscribe(source, bad)
