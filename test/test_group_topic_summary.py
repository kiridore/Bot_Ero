"""Topic summary LLM 触发与 TopicSummaryService 单测。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.group_topic_summary import (  # noqa: E402
    TopicSummaryService,
    should_refresh_topic_summary,
)
from core.llm.llm import ChatResponse, Usage  # noqa: E402


class TestShouldRefreshTopicSummary(unittest.TestCase):
    def test_refresh_pattern(self) -> None:
        self.assertFalse(should_refresh_topic_summary(2))
        self.assertTrue(should_refresh_topic_summary(3))
        self.assertFalse(should_refresh_topic_summary(4))
        self.assertTrue(should_refresh_topic_summary(5))
        self.assertFalse(should_refresh_topic_summary(6))
        self.assertTrue(should_refresh_topic_summary(10))


class TestTopicSummaryService(unittest.TestCase):
    class _FakeLLM:
        def __init__(self) -> None:
            self.calls = 0

        def chat(self, request):
            self.calls += 1
            return ChatResponse(
                message="  摘要一句  ",
                finish_reason="stop",
                usage=Usage(0, 0, 0),
                tool_calls=[],
            )

    class _MockDb:
        def __init__(self, n: int) -> None:
            self.n = n
            self.updates: list[tuple] = []

        def list_topic_message_previews(self, tid: int, limit: int = 30):
            return [f"line{i}" for i in range(self.n)]

        def update_topic_summary(self, topic_id: int, summary: str, updated_at: str) -> None:
            self.updates.append((topic_id, summary, updated_at))

    def test_skips_when_few_previews(self) -> None:
        llm = self._FakeLLM()
        db = self._MockDb(2)
        svc = TopicSummaryService(llm=llm)
        svc.refresh_topic_summary(9, db=db)
        self.assertEqual(llm.calls, 0)
        self.assertEqual(len(db.updates), 0)

    def test_calls_llm_and_writes(self) -> None:
        llm = self._FakeLLM()
        db = self._MockDb(4)
        svc = TopicSummaryService(llm=llm)
        svc.refresh_topic_summary(9, db=db)
        self.assertEqual(llm.calls, 1)
        self.assertEqual(len(db.updates), 1)
        self.assertEqual(db.updates[0][0], 9)
        self.assertEqual(db.updates[0][1], "摘要一句")


if __name__ == "__main__":
    unittest.main(verbosity=2)
