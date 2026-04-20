"""GroupTopicSegmenter 纯逻辑单测（不加载 sentence-transformers）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.group_topic_segmenter import (  # noqa: E402
    GroupTopicSegmenter,
    TopicRecord,
    blob_to_normalized_centroid,
)


class _FakeStore:
    def __init__(self) -> None:
        self.topics: dict[int, TopicRecord] = {}
        self._next_id = 1
        self.assignments: list[tuple] = []

    def list_topics(self, group_id: int) -> list[TopicRecord]:
        return [t for t in self.topics.values() if t.group_id == int(group_id)]

    def insert_topic(
        self,
        group_id: int,
        centroid_blob: bytes,
        message_count: int,
        anchor_preview: str,
        created_at: str,
        updated_at: str,
    ) -> int:
        tid = self._next_id
        self._next_id += 1
        c = blob_to_normalized_centroid(centroid_blob)
        self.topics[tid] = TopicRecord(
            id=tid,
            group_id=int(group_id),
            centroid=c,
            message_count=int(message_count),
            anchor_preview=anchor_preview,
        )
        return tid

    def update_topic_centroid(
        self,
        topic_id: int,
        centroid_blob: bytes,
        message_count: int,
        anchor_preview: str,
        updated_at: str,
    ) -> None:
        c = blob_to_normalized_centroid(centroid_blob)
        old = self.topics[int(topic_id)]
        self.topics[int(topic_id)] = TopicRecord(
            id=old.id,
            group_id=old.group_id,
            centroid=c,
            message_count=int(message_count),
            anchor_preview=anchor_preview,
        )

    def insert_message_assignment(
        self,
        topic_id: int,
        group_id: int,
        message_id: int,
        user_id: int,
        content_preview: str,
        similarity: float | None,
        created_at: str,
    ) -> None:
        self.assignments.append(
            (topic_id, group_id, message_id, user_id, content_preview, similarity, created_at)
        )


class TestGroupTopicSegmenter(unittest.TestCase):
    def test_first_message_creates_topic(self) -> None:
        store = _FakeStore()
        seg = GroupTopicSegmenter(store, similarity_threshold=0.55)
        emb = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
        r = seg.assign_topic(1, "hello world", emb, message_id=10, user_id=20, created_at="t0")
        self.assertTrue(r.is_new_topic)
        self.assertEqual(r.topic_id, 1)
        self.assertEqual(r.similarity, 1.0)
        self.assertEqual(len(store.topics), 1)
        self.assertEqual(len(store.assignments), 1)

    def test_assigns_existing_when_similar(self) -> None:
        store = _FakeStore()
        seg = GroupTopicSegmenter(store, similarity_threshold=0.55)
        e0 = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
        e0 = e0 / np.linalg.norm(e0)
        seg.assign_topic(1, "first", e0, message_id=1, user_id=1, created_at="t0")
        e1 = np.array([0.95, 0.05, 0.0, 0.0], dtype=np.float64)
        e1 = e1 / np.linalg.norm(e1)
        r = seg.assign_topic(1, "second line", e1, message_id=2, user_id=1, created_at="t1")
        self.assertFalse(r.is_new_topic)
        self.assertEqual(r.topic_id, 1)
        self.assertGreater(r.similarity, 0.55)
        t = store.topics[1]
        self.assertEqual(t.message_count, 2)
        expected = (e0 + e1) / 2.0
        expected = expected / np.linalg.norm(expected)
        np.testing.assert_allclose(t.centroid, expected, rtol=1e-5, atol=1e-5)

    def test_new_topic_when_below_threshold(self) -> None:
        store = _FakeStore()
        seg = GroupTopicSegmenter(store, similarity_threshold=0.55)
        e0 = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
        e0 = e0 / np.linalg.norm(e0)
        seg.assign_topic(1, "aa", e0, message_id=1, user_id=1, created_at="t0")
        e1 = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float64)
        e1 = e1 / np.linalg.norm(e1)
        r = seg.assign_topic(1, "bb", e1, message_id=2, user_id=1, created_at="t1")
        self.assertTrue(r.is_new_topic)
        self.assertEqual(r.topic_id, 2)

    def test_text_too_short_raises(self) -> None:
        store = _FakeStore()
        seg = GroupTopicSegmenter(store)
        emb = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
        with self.assertRaises(ValueError):
            seg.assign_topic(1, "x", emb, message_id=1, user_id=1, created_at="t0")


class TestGroupTopicService(unittest.TestCase):
    def test_on_group_message_skips_short_text_without_embed(self) -> None:
        from unittest.mock import MagicMock

        from core.group_topic_service import GroupTopicService

        emb = MagicMock()
        store = _FakeStore()
        svc = GroupTopicService(embedder=emb, store=store, min_text_len=2)
        r = svc.on_group_message(1, 1, 1, [{"type": "text", "data": {"text": "a"}}])
        self.assertIsNone(r)
        emb.embed.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
