"""微博源：基于用户提供响应精简去敏的样本，所有 HTTP 均模拟。"""
import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from plugins import news
from test.helper import MockApiWrapper

KEY = "weibo_6279793937"
NOW = datetime(2026, 10, 30, 18, tzinfo=timezone(timedelta(hours=8)))
LOCAL_NOW = NOW.astimezone().replace(tzinfo=None)
FIXTURE = Path(__file__).parent / "fixtures" / "news_weibo_arknights.json"


def sample():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def payload(cards):
    return {"ok": 1, "data": {"cards": cards}}


def card(nid, age=1, pinned=False, **fields):
    post = {"id": str(nid), "user": {"id": 6279793937},
            "created_at": format_datetime(NOW - timedelta(hours=age)), "text": "公告<br/>正文"}
    post.update(fields)
    return {"card_type": 9, "profile_type_id": "proweibotop_" if pinned else "normal", "mblog": post}


def fetch(*pages):
    responses = [Mock(json=Mock(return_value=p)) for p in pages]
    with patch.object(news, "datetime") as clock, patch.object(news.requests, "get", side_effect=responses) as get:
        clock.now.return_value = LOCAL_NOW
        result = news._fetch_arknights_weibo()
    return result, get


def test_sample_summary_media_time_and_pinned_sort():
    items, get = fetch(sample(), payload([]))
    assert len(items) == 5
    assert items[0].id == "5359748985390844"
    assert items[-1].id == "5357642605922738"  # 旧置顶排到最后
    assert items[0].published_at == (NOW - timedelta(hours=2)).astimezone().replace(tzinfo=None)
    assert items[0].summary == "明日方舟 #明日方舟#\n◤模组升级效果前瞻◢"
    assert items[0].image_url.endswith("/mw2000/006QZngZgy1iikd873k3wj30zk7vcx6p.jpg")
    assert items[1].image_url.endswith("/mw2000/006QZngZgy1iikcen7nhjj31hc0u04qm.jpg")
    assert items[2].image_url.endswith("/orj480/006QZngZgy1iijcqhbfylj31hc0u07wi.jpg")
    assert items[3].image_url.endswith("/large/006QZngZgy1iij9rsfgpfj30zi0k0q5l.jpg")
    assert "全文" in items[1].summary
    assert all(item.link == f"https://m.weibo.cn/status/{item.id}" for item in items)
    assert [c.kwargs["params"]["page"] for c in get.call_args_list] == [1, 2]
    assert all(c.args == (news._WEIBO_URL,) and c.kwargs["timeout"] == 25 for c in get.call_args_list)
    assert all("cookies" not in c.kwargs for c in get.call_args_list)


def test_html_entities_linebreaks_emoji_and_no_scripts():
    assert news._weibo_summary('<p>A &amp; B&nbsp;C</p><div>下一行<br/>末行<img alt="[笑]"/></div><script>bad()</script><style>bad</style>') == 'A & B\xa0C\n\n下一行\n末行[笑]'
    assert news._weibo_summary("字" * 1001) == "字" * 1000 + "…"
    assert news._weibo_summary("<a>@昵称</a>") == "@昵称"


@pytest.mark.parametrize("raw", ["file:///tmp/a", "http://127.0.0.1/a", "https://sinaimg.cn.evil.test/a", "https://evil.test/sinaimg.cn/a", "https://u:p@wx1.sinaimg.cn/a", "https://wx1.sinaimg.cn:8080/a", "https://wx1.sinaimg.cn:0/a", "https://[broken", None])
def test_untrusted_image_urls_are_not_used(raw):
    assert news._weibo_image_url(raw) == ""


def test_image_fallback_and_topic_not_used():
    assert news._weibo_image({"original_pic": "http://wx1.sinaimg.cn/large/a.jpg"}) == "https://wx1.sinaimg.cn/large/a.jpg"
    assert news._weibo_image({"page_info": {"type": "topic", "page_pic": {"url": "https://wx1.sinaimg.cn/a.jpg"}}}) == ""
    assert news._weibo_image({}) == ""
    assert news._weibo_image({"pics": [{"type": "video", "url": "https://wx1.sinaimg.cn/a.jpg"}], "page_info": {"type": "video", "page_pic": {"url": "https://wx1.sinaimg.cn/cover.jpg"}}}) == "https://wx1.sinaimg.cn/cover.jpg"


def test_pagination_dedup_ignores_other_users_and_stops_after_old_page():
    first = [card(10, age=90, pinned=True), card(30), {"card_type": 11}, card(99, user={"id": 1})]
    second = [card(30), card(20), card(10, age=90, pinned=True)]
    third = [card(5, age=60)]
    items, get = fetch(payload(first), payload(second), payload(third))
    assert [i.id for i in items] == ["30", "20", "10", "5"]
    assert get.call_count == 3


def test_title_pinned_does_not_stop_pagination():
    items, get = fetch(payload([card(10, age=90, title={"text": "置顶"})]), payload([card(20)]), payload([]))
    assert [i.id for i in items] == ["20", "10"]
    assert get.call_count == 3


@pytest.mark.parametrize("bad", [{"ok": 0}, [], {"ok": 1, "data": {}}, {"ok": 1, "data": {"cards": {}}}])
def test_bad_payload_is_failure(bad):
    with pytest.raises((ValueError, KeyError)):
        fetch(bad)


@pytest.mark.parametrize("fields", [{"id": "bad"}, {"id": "0"}, {"created_at": "bad"}, {"created_at": "Fri, 30 Oct 2026 12:00:00"}, {"text": None}])
def test_bad_critical_fields_fail_entire_source(fields):
    with pytest.raises(ValueError):
        fetch(payload([card(10)]), payload([card(11, **fields)]))


def test_repeated_page_and_page_limit_fail_instead_of_partial_success():
    with pytest.raises(ValueError, match="无进展"):
        fetch(payload([card(10)]), payload([card(10)]))
    with pytest.raises(ValueError, match="超过20页"):
        fetch(*(payload([card(i)]) for i in range(100, 80, -1)))


@pytest.mark.parametrize("error", [requests.HTTPError("432"), ValueError("not JSON")])
def test_network_or_json_failure_propagates(error):
    response = Mock()
    if isinstance(error, requests.HTTPError):
        response.raise_for_status.side_effect = error
    else:
        response.json.side_effect = error
    with patch.object(news.requests, "get", return_value=response), pytest.raises(type(error)):
        news._fetch_arknights_weibo()


def test_registered_weibo_source_initializes_then_pushes_once():
    plugin = news.NewsPlugin({"post_type": "meta_event"})
    db = plugin.dbmanager
    try:
        db.conn.execute("DELETE FROM news_subscriptions")
        db.conn.execute("DELETE FROM news_push_state")
        db.conn.commit()
        db.news.subscribe(123, KEY)
        db.news.subscribe(456, "ff14")
        plugin.api = Mock()
        plugin.api.send_msg.return_value = 1
        baseline = sample()
        updated = sample()
        updated["data"]["cards"].append(card(5359748985390845, age=1))
        pages = [baseline, payload([]), updated, payload([]), updated, payload([])]
        responses = [Mock(json=Mock(return_value=p)) for p in pages]
        with patch.object(news, "_SOURCES", [news._SOURCES[1]]), \
                patch.object(news, "datetime") as clock, \
                patch.object(news.requests, "get", side_effect=responses):
            clock.now.return_value = LOCAL_NOW
            plugin._poll_and_push()
            plugin.api.send_msg.assert_not_called()
            plugin._poll_and_push()
            plugin._poll_and_push()
        plugin.api.send_msg.assert_called_once()
        segments = plugin.api.send_msg.call_args.args
        assert [s["data"]["qq"] for s in segments if s["type"] == "at"] == ["123"]
        body = next(s["data"]["text"] for s in segments if s["type"] == "text")
        assert "【明日方舟官方微博】" in body
        assert "公告\n正文" in body
        assert "https://m.weibo.cn/status/5359748985390845" in body
        assert db.news.get_cursor(KEY) == "5359748985390845"
    finally:
        db.conn.execute("DELETE FROM news_subscriptions")
        db.conn.execute("DELETE FROM news_push_state")
        db.conn.commit()
        db.conn.close()


def test_weibo_failure_keeps_its_cursor_and_ff14_still_pushes():
    plugin = news.NewsPlugin({"post_type": "meta_event"})
    db = plugin.dbmanager
    try:
        db.conn.execute("DELETE FROM news_subscriptions")
        db.conn.execute("DELETE FROM news_push_state")
        db.conn.commit()
        db.news.subscribe(123, "ff14")
        db.news.save_cursor("ff14", "10")
        db.news.save_cursor(KEY, "5359748985390844")
        ctx = {"post_type": "meta_event"}
        plugin.api = MockApiWrapper(ctx)
        record = plugin.api.send_msg
        plugin.api.send_msg = lambda *segments: (record(*segments), 1)[1]
        item = news.NewsItem("11", "FF14新消息", "正文", "https://example.invalid/11", "", datetime.now())
        failed = news.NewsSource(KEY, "微博", "微博", Mock(side_effect=requests.HTTPError("432")))
        good = news.NewsSource("ff14", "FF14", "FF14", lambda: [item])
        with patch.object(news, "_SOURCES", [failed, good]):
            plugin._poll_and_push()
        assert db.news.get_cursor(KEY) == "5359748985390844"
        assert db.news.get_cursor("ff14") == "11"
        assert len(plugin.api.sent_messages) == 1
    finally:
        db.conn.execute("DELETE FROM news_subscriptions")
        db.conn.execute("DELETE FROM news_push_state")
        db.conn.commit()
        db.conn.close()
