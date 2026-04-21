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
    RECENT_EMBEDDING_MAX,
    GroupTopicSegmenter,
    TopicRecord,
    blob_to_normalized_centroid,
    should_create_new_topic,
)


def _norm(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float64).ravel()
    n = float(np.linalg.norm(v))
    return v if n <= 0.0 else v / n


class _FakeStore:
    def __init__(self) -> None:
        self.topics: dict[int, TopicRecord] = {}
        self._recent_by_topic: dict[int, list[np.ndarray]] = {}
        self._next_id = 1
        self.assignments: list[tuple] = []

    def load_fixture_topic(
        self,
        tid: int,
        group_id: int,
        centroid_vec: np.ndarray,
        recent_vecs: list[np.ndarray],
        message_count: int,
        anchor: str = "fixture",
    ) -> None:
        c = _norm(centroid_vec)
        rev = [_norm(v).copy() for v in recent_vecs]
        self._recent_by_topic[tid] = [v.copy() for v in rev]
        self.topics[tid] = TopicRecord(
            id=tid,
            group_id=int(group_id),
            centroid=c,
            message_count=int(message_count),
            anchor_preview=anchor,
            recent_embeddings=(),
        )
        self._next_id = max(self._next_id, tid + 1)

    def list_topics(self, group_id: int) -> list[TopicRecord]:
        out: list[TopicRecord] = []
        for t in sorted(self.topics.values(), key=lambda x: x.id):
            if t.group_id != int(group_id):
                continue
            rev = self._recent_by_topic.get(t.id, [])
            tail = rev[-RECENT_EMBEDDING_MAX:]
            recent = tuple(np.asarray(v, dtype=np.float64).copy() for v in tail)
            out.append(
                TopicRecord(
                    id=t.id,
                    group_id=t.group_id,
                    centroid=t.centroid,
                    message_count=t.message_count,
                    anchor_preview=t.anchor_preview,
                    recent_embeddings=recent,
                )
            )
        return out

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
        self._recent_by_topic[tid] = []
        self.topics[tid] = TopicRecord(
            id=tid,
            group_id=int(group_id),
            centroid=c,
            message_count=int(message_count),
            anchor_preview=anchor_preview,
            recent_embeddings=(),
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
            recent_embeddings=(),
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
        msg_embedding_blob: bytes | None = None,
    ) -> None:
        self.assignments.append(
            (
                topic_id,
                group_id,
                message_id,
                user_id,
                content_preview,
                similarity,
                created_at,
                msg_embedding_blob,
            )
        )
        lst = self._recent_by_topic.setdefault(int(topic_id), [])
        if msg_embedding_blob:
            vec = blob_to_normalized_centroid(bytes(msg_embedding_blob))
            lst.append(vec)
            while len(lst) > RECENT_EMBEDDING_MAX:
                lst.pop(0)


class TestShouldCreateNewTopic(unittest.TestCase):
    def test_empty_recent_returns_false(self) -> None:
        t = TopicRecord(
            id=1,
            group_id=1,
            centroid=np.array([1.0, 0.0, 0.0, 0.0]),
            message_count=1,
            anchor_preview="",
            recent_embeddings=(),
        )
        msg = _norm(np.array([0.0, 1.0, 0.0, 0.0]))
        self.assertFalse(should_create_new_topic(msg, t))

    def test_high_similarity_to_recent_returns_false(self) -> None:
        ex = _norm(np.array([1.0, 0.0, 0.0, 0.0]))
        t = TopicRecord(1, 1, ex, 5, "", recent_embeddings=(ex, ex, ex))
        msg = _norm(np.array([0.98, 0.05, 0.0, 0.0]))
        self.assertFalse(should_create_new_topic(msg, t))

    def test_orthogonal_to_recent_returns_true(self) -> None:
        ex = _norm(np.array([1.0, 0.0, 0.0, 0.0]))
        t = TopicRecord(1, 1, ex, 5, "", recent_embeddings=(ex, ex, ex))
        msg = _norm(np.array([0.0, 1.0, 0.0, 0.0]))
        self.assertTrue(should_create_new_topic(msg, t))

    def test_last_vec_gate(self) -> None:
        ex = _norm(np.array([1.0, 0.0, 0.0, 0.0]))
        mid = _norm(np.array([1.0, 0.15, 0.0, 0.0]))
        t = TopicRecord(1, 1, ex, 5, "", recent_embeddings=(ex, mid))
        msg = _norm(np.array([0.25, 1.0, 0.0, 0.0]))
        self.assertTrue(should_create_new_topic(msg, t, sim_recent_min=0.99, sim_last_min=0.6))


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
        self.assertIsNotNone(store.assignments[0][7])

    def test_assigns_existing_ema_update(self) -> None:
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
        expected = _norm(0.8 * e0 + 0.2 * e1)
        np.testing.assert_allclose(t.centroid, expected, rtol=1e-5, atol=1e-5)

    def test_new_topic_when_below_centroid_threshold(self) -> None:
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

    def test_splits_when_centroid_ok_but_recent_diverges(self) -> None:
        store = _FakeStore()
        ex = _norm(np.array([1.0, 0.0, 0.0, 0.0]))
        cy = _norm(np.array([0.2, 1.0, 0.0, 0.0]))
        store.load_fixture_topic(
            1,
            1,
            cy,
            [ex.copy() for _ in range(5)],
            message_count=10,
            anchor="fixture",
        )
        seg = GroupTopicSegmenter(store, similarity_threshold=0.3)
        emb = _norm(np.array([0.0, 1.0, 0.0, 0.0]))
        r = seg.assign_topic(1, "hello there", emb, message_id=99, user_id=1, created_at="t_split")
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
