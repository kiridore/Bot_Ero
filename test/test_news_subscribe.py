"""新闻订阅插件测试：指令行为（AC01）与订阅驱动推送（AC02）。

运行: pytest test/test_news_subscribe.py
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from plugins import news as news_mod
from plugins.news import NewsItem, NewsPlugin, NewsSource
from test.helper import MockApiWrapper, make_group_message, make_private_message

USER = 123456


def _item(nid: int, hours_ago: float = 0.5) -> NewsItem:
    return NewsItem(
        id=str(nid),
        title=f"标题{nid}",
        summary=f"摘要{nid}",
        link=f"https://example.invalid/{nid}",
        image_url="",
        published_at=datetime.now() - timedelta(hours=hours_ago),
    )


def _fake_source(items: list[NewsItem]) -> NewsSource:
    def fetch():
        return list(items)

    return NewsSource(key="test", name="测试源", push_header="【测试快讯】", fetch=fetch)


class _Base(unittest.TestCase):
    def setUp(self):
        # conftest 提供会话级临时库；用例间清空新闻两张表
        db = NewsPlugin(make_group_message("/订阅", USER)).dbmanager
        db.cur.execute("DELETE FROM news_subscriptions")
        db.cur.execute("DELETE FROM news_push_state")
        db.conn.commit()
        db.conn.close()

    def _run_command(self, text: str, ctx=None):
        ctx = ctx or make_group_message(text, USER)
        plugin = NewsPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        self.assertTrue(plugin.match("message"), f"指令应被匹配: {text}")
        plugin.handle()
        return plugin

    def _sent_texts(self, plugin) -> list[str]:
        return [
            s["data"]["text"]
            for m in plugin.api.sent_messages
            for s in m[1]
            if s["type"] == "text"
        ]


class TestCommands(_Base):
    def test_list_shows_source_and_status(self):
        plugin = self._run_command("/订阅")
        body = self._sent_texts(plugin)[0]
        self.assertIn("1. FF14 国服官网", body)
        self.assertIn("2. 明日方舟官方微博（未订阅）", body)
        self.assertNotIn("已订阅", body)
        self._run_command("/订阅 1")
        plugin = self._run_command("/订阅")
        self.assertIn("1. FF14 国服官网（已订阅）", self._sent_texts(plugin)[0])

    def test_weibo_subscription_is_independent(self):
        original = self._run_command("/订阅 1")
        original.dbmanager.news.save_cursor("ff14", "10")
        self._run_command("/订阅 2")
        duplicate = self._run_command("/订阅 2")
        self.assertIn("你已订阅", self._sent_texts(duplicate)[0])
        listed = self._run_command("/订阅")
        self.assertIn("2. 明日方舟官方微博（已订阅）", self._sent_texts(listed)[0])
        removed = self._run_command("/退订 2")
        self.assertTrue(removed.dbmanager.news.is_subscribed(USER, "ff14"))
        self.assertFalse(removed.dbmanager.news.is_subscribed(USER, "weibo_6279793937"))
        self.assertEqual(removed.dbmanager.news.get_cursor("ff14"), "10")
        private = self._run_command("/订阅 2", make_private_message("/订阅 2", USER))
        self.assertFalse(private.dbmanager.news.is_subscribed(USER, "weibo_6279793937"))

    def test_subscribe_idempotent(self):
        self._run_command("/订阅 1")
        plugin = self._run_command("/订阅 1")
        self.assertIn("你已订阅", self._sent_texts(plugin)[0])
        db = NewsPlugin(make_group_message("/订阅", USER)).dbmanager
        db.cur.execute(
            "SELECT COUNT(*) FROM news_subscriptions WHERE user_id = ? AND source_id = 'ff14'", (USER,)
        )
        self.assertEqual(db.cur.fetchone()[0], 1)
        db.conn.close()

    def test_unsubscribe_flow(self):
        self._run_command("/订阅 1")
        plugin = self._run_command("/退订 1")
        self.assertIn("已退订", self._sent_texts(plugin)[0])
        plugin = self._run_command("/退订 1")
        self.assertIn("你尚未订阅", self._sent_texts(plugin)[0])

    def test_unsubscribe_without_arg_shows_usage(self):
        plugin = self._run_command("/退订")
        self.assertIn("用法", self._sent_texts(plugin)[0])

    def test_invalid_number(self):
        plugin = self._run_command("/订阅 99")
        self.assertIn("没有该编号", self._sent_texts(plugin)[0])
        plugin = self._run_command("/订阅 abc")
        self.assertIn("没有该编号", self._sent_texts(plugin)[0])

    def test_private_chat_rejected_without_write(self):
        ctx = make_private_message("/订阅 1", USER)
        plugin = NewsPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        self.assertTrue(plugin.match("message"))
        plugin.handle()
        self.assertIn("仅限群聊", self._sent_texts(plugin)[0])
        db = NewsPlugin(ctx).dbmanager
        db.cur.execute("SELECT COUNT(*) FROM news_subscriptions")
        self.assertEqual(db.cur.fetchone()[0], 0)
        db.conn.close()

    def test_extra_argument_rejected(self):
        plugin = self._run_command("/订阅 1 2")
        self.assertIn("没有该编号", self._sent_texts(plugin)[0])
        self.assertFalse(plugin.dbmanager.news.is_subscribed(USER, "ff14"))

    def test_subscription_shared_across_groups(self):
        self._run_command("/订阅 1")
        other = self._run_command("/订阅", make_group_message("/订阅", USER, group_id=999))
        self.assertIn("（已订阅）", self._sent_texts(other)[0])
        private = self._run_command("/退订 1", make_private_message("/退订 1", USER))
        self.assertTrue(private.dbmanager.news.is_subscribed(USER, "ff14"))

    def test_old_ff_news_command_not_matched(self):
        ctx = make_group_message("/FF新闻", USER)
        plugin = NewsPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        self.assertFalse(plugin.match("message"))


class TestPush(_Base):
    def _poll(self, result=1):
        ctx = {"post_type": "meta_event", "meta_event_type": "heartbeat"}
        plugin = NewsPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        record = plugin.api.send_msg
        plugin.api.send_msg = lambda *segments: (record(*segments), result)[1]
        plugin._poll_and_push()
        return plugin

    def _subscribe_test_source(self, *users: int):
        db = NewsPlugin(make_group_message("/订阅", USER)).dbmanager
        for u in users:
            db.news.subscribe(u, "test")
        db.conn.close()

    def test_default_group_routing_and_image(self):
        from dataclasses import replace
        from core import context
        from core.api import ApiWrapper
        self._subscribe_test_source(USER)
        with patch.object(news_mod, "_SOURCES", [_fake_source([_item(10)])]):
            self._poll()
        ctx = {"post_type": "meta_event", "meta_event_type": "heartbeat"}
        plugin = NewsPlugin(ctx)
        item = replace(_item(11), image_url="https://example.invalid/news.jpg")
        with patch.object(news_mod, "_SOURCES", [_fake_source([item])]), \
                patch.object(context, "DEFAULT_GROUP_ID", 987654), \
                patch.object(ApiWrapper, "_build_title_prefix", return_value="称号"), \
                patch.object(ApiWrapper, "call_api", return_value={"status": "ok", "data": {"message_id": 42}}) as call:
            plugin._poll_and_push()
        action, params = call.call_args.args
        self.assertEqual(action, "send_group_msg")
        self.assertEqual(params["group_id"], 987654)
        self.assertEqual(params["message"][0]["data"]["text"], "称号 ")
        self.assertEqual(params["message"][-1]["type"], "image")

    def test_first_run_records_cursor_without_push(self):
        src = _fake_source([_item(10), _item(9)])
        with patch.object(news_mod, "_SOURCES", [src]):
            plugin = self._poll()
        self.assertEqual(plugin.api.sent_messages, [])
        db = NewsPlugin(make_group_message("/订阅", USER)).dbmanager
        self.assertEqual(db.news.get_cursor("test"), "10")
        db.conn.close()

    def test_no_subscriber_no_push_but_cursor_advances(self):
        self._subscribe_test_source(USER)  # 订阅者存在但先首跑记游标
        src = _fake_source([_item(10)])
        with patch.object(news_mod, "_SOURCES", [src]):
            self._poll()
        src = _fake_source([_item(11)])
        with patch.object(news_mod, "_SOURCES", [src]):
            db = NewsPlugin(make_group_message("/订阅", USER)).dbmanager
            db.cur.execute("DELETE FROM news_subscriptions")
            db.conn.commit()
            db.conn.close()
            plugin = self._poll()
        self.assertEqual(plugin.api.sent_messages, [])
        db = NewsPlugin(make_group_message("/订阅", USER)).dbmanager
        self.assertEqual(db.news.get_cursor("test"), "11")  # 游标仍前进
        db.conn.close()

    def test_push_ats_all_subscribers_with_body(self):
        self._subscribe_test_source(111, 222)
        src = _fake_source([_item(10)])
        with patch.object(news_mod, "_SOURCES", [src]):
            self._poll()
        src = _fake_source([_item(11)])
        with patch.object(news_mod, "_SOURCES", [src]):
            plugin = self._poll()
        self.assertEqual(len(plugin.api.sent_messages), 1)
        segs = plugin.api.sent_messages[0][1]
        ats = [s for s in segs if s["type"] == "at"]
        self.assertEqual([s["data"]["qq"] for s in ats], ["111", "222"])
        body = segs[-1]["data"]["text"]
        self.assertIn("标题11", body)
        self.assertIn("https://example.invalid/11", body)

    def test_same_item_not_pushed_twice(self):
        self._subscribe_test_source(USER)
        src = _fake_source([_item(10)])
        with patch.object(news_mod, "_SOURCES", [src]):
            self._poll()
        with patch.object(news_mod, "_SOURCES", [src]):
            plugin = self._poll()
        self.assertEqual(len(plugin.api.sent_messages), 0)

    def test_stale_item_skipped(self):
        self._subscribe_test_source(USER)
        src = _fake_source([_item(10)])
        with patch.object(news_mod, "_SOURCES", [src]):
            self._poll()
        src = _fake_source([_item(11, hours_ago=72)])
        with patch.object(news_mod, "_SOURCES", [src]):
            plugin = self._poll()
        self.assertEqual(plugin.api.sent_messages, [])
        db = NewsPlugin(make_group_message("/订阅", USER)).dbmanager
        self.assertEqual(db.news.get_cursor("test"), "11")
        db.conn.close()

    def test_multiple_new_items_pushed_one_by_one_oldest_first(self):
        self._subscribe_test_source(USER)
        src = _fake_source([_item(10)])
        with patch.object(news_mod, "_SOURCES", [src]):
            self._poll()
        src = _fake_source([_item(12), _item(11), _item(10)])  # 新→旧乱序混入旧条目
        with patch.object(news_mod, "_SOURCES", [src]):
            plugin = self._poll()
        texts = self._sent_texts(plugin)
        self.assertEqual(len(plugin.api.sent_messages), 2)
        self.assertIn("标题11", texts[0])
        self.assertIn("标题12", texts[1])

    def test_cursor_never_moves_backwards(self):
        self._subscribe_test_source(USER)
        for ids in ([10], [9], [10]):
            with patch.object(news_mod, "_SOURCES", [_fake_source([_item(i) for i in ids])]):
                plugin = self._poll()
                self.assertEqual(plugin.api.sent_messages, [])
                self.assertEqual(plugin.dbmanager.news.get_cursor("test"), "10")

    def test_failed_send_retries_without_losing_item(self):
        self._subscribe_test_source(USER)
        with patch.object(news_mod, "_SOURCES", [_fake_source([_item(10)])]):
            self._poll()
        with patch.object(news_mod, "_SOURCES", [_fake_source([_item(11)])]):
            failed = self._poll(result=0)
            self.assertEqual(failed.dbmanager.news.get_cursor("test"), "10")
            success = self._poll()
            self.assertEqual(success.dbmanager.news.get_cursor("test"), "11")
            self.assertEqual(len(success.api.sent_messages), 1)
            self.assertEqual(self._poll().api.sent_messages, [])

    def test_future_item_waits(self):
        self._subscribe_test_source(USER)
        with patch.object(news_mod, "_SOURCES", [_fake_source([_item(10)])]):
            self._poll()
        with patch.object(news_mod, "_SOURCES", [_fake_source([_item(11, -2)])]):
            plugin = self._poll()
        self.assertEqual(plugin.api.sent_messages, [])
        self.assertEqual(plugin.dbmanager.news.get_cursor("test"), "10")

    def test_half_hour_schedule_and_match_has_no_side_effects(self):
        ctx = {"post_type": "meta_event", "meta_event_type": "heartbeat"}
        plugin = NewsPlugin(ctx)
        with patch.object(news_mod.TimedHeartbeatPlugin, "_last_run_minute", {}), \
                patch.object(news_mod, "datetime") as clock, \
                patch.object(plugin, "_poll_and_push") as poll:
            for minute, expected in ((0, True), (15, False), (30, True)):
                clock.now.return_value = datetime(2026, 1, 1, 10, minute)
                self.assertEqual(plugin.match("meta"), expected)
                self.assertEqual(plugin.match("meta"), expected)
                plugin.handle()
                plugin.handle()
            self.assertEqual(poll.call_count, 2)

    def test_fetch_failure_skips_source_and_keeps_cursor(self):
        self._subscribe_test_source(USER)
        src = _fake_source([_item(10)])
        with patch.object(news_mod, "_SOURCES", [src]):
            self._poll()

        def boom():
            raise RuntimeError("network down")

        broken = NewsSource(key="test", name="测试源", push_header="【测试快讯】", fetch=boom)
        with patch.object(news_mod, "_SOURCES", [broken]):
            self._poll()  # 失败：不抛、不发、游标不动
        src = _fake_source([_item(11)])
        with patch.object(news_mod, "_SOURCES", [src]):
            plugin = self._poll()  # 恢复后 11 仍是新条目，正常推送
        self.assertEqual(len(plugin.api.sent_messages), 1)
        self.assertIn("标题11", self._sent_texts(plugin)[0])


class TestFetch(unittest.TestCase):
    def test_reads_all_pages_and_sorts_pinned_items(self):
        def response(rows):
            return Mock(json=Mock(return_value={"Code": "0", "PageCount": 2, "Data": rows}))
        def row(nid):
            return {"Id": nid, "PublishDate": "2026/10/28 12:00:00", "Title": f"新闻{nid}"}
        with patch.object(news_mod.requests, "get", side_effect=[response([row(1), row(3)]), response([row(4), row(3)])]) as get:
            items = news_mod._fetch_ff14()
        self.assertEqual([it.id for it in items], ["4", "3", "1"])
        self.assertEqual([c.kwargs["params"]["pageIndex"] for c in get.call_args_list], ["0", "1"])
        self.assertTrue(all(c.kwargs["timeout"] == 25 for c in get.call_args_list))

    def test_api_error_and_invalid_data_fail_without_partial_result(self):
        for payload in ({"Code": "1"}, {"Code": "0", "Data": [{"Id": "bad", "PublishDate": "bad"}]}):
            with self.subTest(payload=payload), patch.object(news_mod.requests, "get", return_value=Mock(json=Mock(return_value=payload))):
                with self.assertRaises(ValueError):
                    news_mod._fetch_ff14()
