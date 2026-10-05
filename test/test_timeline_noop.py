"""时间线上报开关（社区版 T0.3）：timeline.url 留空 → emit/retract 完全 no-op；有配置 → 行为不变。"""
import sys
import unittest
from unittest import mock

import core.timeline_client as timeline_client


class TestTimelineNoop(unittest.TestCase):
    """空配置：两个出网出口（_post/_request）零请求、零异常。"""

    def test_emit_event_no_http_when_url_empty(self):
        with mock.patch.object(timeline_client, "TIMELINE_URL", ""), \
                mock.patch.object(timeline_client, "requests") as req:
            timeline_client.emit_event("checkin", actor_id=123, title="打卡")
            req.post.assert_not_called()
            req.request.assert_not_called()

    def test_retract_event_no_http_when_url_empty(self):
        with mock.patch.object(timeline_client, "TIMELINE_URL", ""), \
                mock.patch.object(timeline_client, "requests") as req:
            timeline_client.retract_event("checkin", dedup_key="checkin:123:2026-09-18")
            req.post.assert_not_called()
            req.request.assert_not_called()


class TestTimelineConfigured(unittest.TestCase):
    """有配置（私有形态）：URL 拼接与 Bearer 头回归。"""

    def test_emit_event_posts_to_event_server(self):
        resp = mock.Mock()
        with mock.patch.object(timeline_client, "TIMELINE_URL", "http://example.com"), \
                mock.patch.object(timeline_client, "TIMELINE_TOKEN", "tok"), \
                mock.patch.object(timeline_client, "requests") as req:
            req.post.return_value = resp
            timeline_client.emit_event("checkin", actor_id=123, title="打卡")
            req.post.assert_called_once()
            args, kwargs = req.post.call_args
            self.assertEqual(args[0], "http://example.com/api/timeline/events")
            self.assertEqual(kwargs["headers"]["Authorization"], "Bearer tok")
            self.assertEqual(kwargs["json"]["source"], "checkin")

    def test_retract_event_deletes_by_key(self):
        with mock.patch.object(timeline_client, "TIMELINE_URL", "http://example.com"), \
                mock.patch.object(timeline_client, "TIMELINE_TOKEN", "tok"), \
                mock.patch.object(timeline_client, "requests") as req:
            timeline_client.retract_event("checkin", dedup_key="k1")
            req.request.assert_called_once_with(
                "delete",
                "http://example.com/api/timeline/events/by-key",
                headers={"Authorization": "Bearer tok", "Content-Type": "application/json"},
                timeout=5,
                params={"source": "checkin", "key": "k1"},
            )


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=2))
