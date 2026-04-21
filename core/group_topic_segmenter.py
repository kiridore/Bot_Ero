"""群聊话题划分：向量与质心运算 + 持久化接口（不依赖 Embedder，便于单测）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence, runtime_checkable

import numpy as np

from core.logger import logger

DEFAULT_SIMILARITY_THRESHOLD = 0.55
MIN_TEXT_LEN_FOR_TOPIC = 2


@dataclass(frozen=True)
class TopicRecord:
    """群内一条话题及其质心。"""

    id: int
    group_id: int
    centroid: np.ndarray  # shape (dim,), float64, L2 归一化
    message_count: int
    anchor_preview: str


@dataclass(frozen=True)
class AssignmentResult:
    """单条消息划分结果。"""

    topic_id: int
    is_new_topic: bool
    similarity: float
    text_preview: str


@runtime_checkable
class TopicSegmenterStore(Protocol):
    def list_topics(self, group_id: int) -> list[TopicRecord]:
        ...

    def insert_topic(
        self,
        group_id: int,
        centroid_blob: bytes,
        message_count: int,
        anchor_preview: str,
        created_at: str,
        updated_at: str,
    ) -> int:
        ...

    def update_topic_centroid(
        self,
        topic_id: int,
        centroid_blob: bytes,
        message_count: int,
        anchor_preview: str,
        updated_at: str,
    ) -> None:
        ...

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
        ...


def _normalize(vec: np.ndarray) -> np.ndarray:
    v = np.asarray(vec, dtype=np.float64).ravel()
    n = float(np.linalg.norm(v))
    if n <= 0.0:
        return v
    return v / n


def embedding_to_f32_blob(emb: Sequence[float] | np.ndarray) -> bytes:
    arr = np.asarray(emb, dtype=np.float32).ravel()
    return arr.tobytes()


def blob_to_normalized_centroid(blob: bytes) -> np.ndarray:
    v = np.frombuffer(blob, dtype=np.float32).astype(np.float64).ravel()
    return _normalize(v)


class GroupTopicSegmenter:
    """对单条已向量化的文本，归入已有 topic 或新建 topic。"""

    def __init__(
        self,
        store: TopicSegmenterStore,
        *,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        max_preview_len: int = 500,
    ) -> None:
        self._store = store
        self._threshold = float(similarity_threshold)
        self._max_preview = int(max_preview_len)

    def assign_topic(
        self,
        group_id: int,
        text: str,
        embedding: Sequence[float] | np.ndarray,
        *,
        message_id: int,
        user_id: int,
        created_at: str,
    ) -> AssignmentResult:
        raw = (text or "").strip()
        if len(raw) < MIN_TEXT_LEN_FOR_TOPIC:
            raise ValueError("text too short for topic assignment")

        emb = _normalize(np.asarray(embedding, dtype=np.float64).ravel())
        preview = raw[: self._max_preview]

        topics = self._store.list_topics(int(group_id))
        best_id: int | None = None
        best_sim = -1.0
        best_record: TopicRecord | None = None
        sim_pairs: list[tuple[int, float]] = []

        for t in topics:
            sim = float(np.dot(emb, t.centroid))
            sim_pairs.append((t.id, sim))
            if sim > best_sim:
                best_sim = sim
                best_id = t.id
                best_record = t

        if sim_pairs:
            sims_fmt = " ".join(f"{tid}:{s:.4f}" for tid, s in sim_pairs)
        else:
            sims_fmt = "(no topics)"
        logger.debug(
            "[group_topic_embed] group=%s user=%s msg_id=%s dim=%s threshold=%.3f | vs_topics: %s | best_topic=%s best_sim=%.4f preview=%r",
            group_id,
            user_id,
            message_id,
            int(emb.shape[0]),
            self._threshold,
            sims_fmt,
            best_id if best_id is not None else "-",
            best_sim,
            preview[:120],
        )

        if not topics or best_record is None or best_sim < self._threshold:
            blob = embedding_to_f32_blob(emb)
            tid = self._store.insert_topic(
                int(group_id),
                blob,
                1,
                preview,
                created_at,
                created_at,
            )
            self._store.insert_message_assignment(
                tid,
                int(group_id),
                int(message_id),
                int(user_id),
                preview,
                None,
                created_at,
            )
            return AssignmentResult(
                topic_id=tid,
                is_new_topic=True,
                similarity=1.0,
                text_preview=preview,
            )

        assert best_record is not None and best_id is not None
        n = int(best_record.message_count)
        merged = (n * best_record.centroid + emb) / (n + 1)
        merged = _normalize(merged)
        new_count = n + 1
        new_blob = embedding_to_f32_blob(merged)
        self._store.update_topic_centroid(
            int(best_id),
            new_blob,
            new_count,
            preview,
            created_at,
        )
        self._store.insert_message_assignment(
            int(best_id),
            int(group_id),
            int(message_id),
            int(user_id),
            preview,
            float(best_sim),
            created_at,
        )
        return AssignmentResult(
            topic_id=int(best_id),
            is_new_topic=False,
            similarity=float(best_sim),
            text_preview=preview,
        )
