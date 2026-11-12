"""字符串格式（CQ 码）消息解析：把 message 字符串切成消息段列表。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.cq import parse
from core.event import Event


class TestCqParse(unittest.TestCase):
    def test_plain_text(self):
        self.assertEqual(parse("你好"), [{"type": "text", "data": {"text": "你好"}}])

    def test_at_segment(self):
        self.assertEqual(parse("[CQ:at,qq=100000002]"),
                         [{"type": "at", "data": {"qq": "100000002"}}])

    def test_text_then_at(self):
        self.assertEqual(parse(".hp 满 [CQ:at,qq=100]"), [
            {"type": "text", "data": {"text": ".hp 满 "}},
            {"type": "at", "data": {"qq": "100"}},
        ])

    def test_multiple_segments(self):
        kinds = [seg["type"] for seg in parse("[CQ:at,qq=all][CQ:image,file=1.jpg]看这个")]
        self.assertEqual(kinds, ["at", "image", "text"])

    def test_escaping(self):
        self.assertEqual(parse("&#91;x&#93; &amp;data")[0]["data"]["text"], "[x] &data")

    def test_param_escaping(self):
        seg = parse("[CQ:share,title=a&#44;b,url=http://x?a=1&amp;b=2]")[0]
        self.assertEqual(seg["data"]["title"], "a,b")
        self.assertEqual(seg["data"]["url"], "http://x?a=1&b=2")

    def test_array_passthrough(self):
        segments = [{"type": "text", "data": {"text": "hi"}}]
        self.assertIs(parse(segments), segments)

    def test_empty(self):
        self.assertEqual(parse(""), [])
        self.assertEqual(parse(None), [])

    def test_event_normalizes_string_message(self):
        event = Event({"message": ".hp 满 [CQ:at,qq=100000002]"})
        self.assertEqual([seg["type"] for seg in event.message], ["text", "at"])

    def test_event_keeps_array_message(self):
        raw = {"message": [{"type": "text", "data": {"text": "hi"}}]}
        self.assertEqual(Event(raw).message, raw["message"])
