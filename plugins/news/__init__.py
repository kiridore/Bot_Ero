from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit
from typing import Callable
from threading import Lock

import requests

from core.base import TimedHeartbeatPlugin
from core.cq import at, image, text
from core.logger import logger
from core.utils import register_plugin
from plugins.news.weibo_browser import WEIBO_UID, fetch_homepage

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


class _WeiboTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        if self.hidden:
            return
        if tag in ("br", "p", "div"):
            self.parts.append("\n")
        elif tag == "img":
            self.parts.append(dict(attrs).get("alt") or "")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in ("p", "div"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _weibo_summary(raw: str) -> str:
    parser = _WeiboTextParser()
    parser.feed(raw)
    parser.close()
    body = "\n".join(line.strip() for line in "".join(parser.parts).splitlines()).strip()
    return body[:1000] + "…" if len(body) > 1000 else body


def _weibo_image_url(raw) -> str:
    if not isinstance(raw, str):
        return ""
    try:
        url = urlsplit(raw)
        host = url.hostname or ""
        if (url.scheme not in ("http", "https") or url.username or url.password or url.port is not None
                or not (host == "sinaimg.cn" or host.endswith(".sinaimg.cn"))):
            return ""
        return urlunsplit(("https", url.netloc, url.path, url.query, ""))
    except ValueError:
        return ""


def _weibo_image(mblog: dict) -> str:
    for pic in mblog.get("pics") or []:
        if pic.get("type") == "video":
            continue
        # 只取第一张正文图片，拒绝不可信地址后继续尝试同图缩略地址。
        for raw in ((pic.get("large") or {}).get("url"), pic.get("url")):
            if url := _weibo_image_url(raw):
                return url
        break
    if url := _weibo_image_url(mblog.get("original_pic")):
        return url
    page = mblog.get("page_info") or {}
    if page.get("type") in ("video", "article"):
        return _weibo_image_url((page.get("page_pic") or {}).get("url"))
    return ""


def _fetch_arknights_weibo() -> list[NewsItem]:
    # shortcut: 仅处理首页；若需补抓首页之外消息，应先取得可合法翻页的来源。
    cards = fetch_homepage()["data"]["cards"]
    items = {}
    for card in cards:
        if card.get("card_type") != 9:
            continue
        mblog = card["mblog"]
        if str(mblog["user"]["id"]) != WEIBO_UID:
            continue
        nid = str(mblog["id"])
        if not nid.isascii() or not nid.isdigit() or int(nid) <= 0:
            raise ValueError("微博编号无效")
        published = parsedate_to_datetime(mblog["created_at"])
        if published.tzinfo is None:
            raise ValueError("微博发布时间缺少时区")
        published = published.astimezone().replace(tzinfo=None)
        raw_text = mblog["text"]
        if not isinstance(raw_text, str):
            raise ValueError("微博正文无效")
        items[nid] = NewsItem(
            id=nid, title="明日方舟Arknights 发布微博", summary=_weibo_summary(raw_text),
            link=f"https://m.weibo.cn/status/{nid}", image_url=_weibo_image(mblog),
            published_at=published,
        )
    if cards and not items:
        raise ValueError("微博首页没有目标账号内容")
    return sorted(items.values(), key=lambda item: int(item.id), reverse=True)


# 消息源编号必须稳定；新增源只追加，不能重排已有项。
_SOURCES: list[NewsSource] = [
    NewsSource(key="ff14", name="FF14 国服官网", push_header="【FF14 官网快讯】", fetch=_fetch_ff14),
    NewsSource(key="weibo_6279793937", name="明日方舟官方微博", push_header="【明日方舟官方微博】",
               fetch=_fetch_arknights_weibo),
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
