"""群聊话题划分：向量与滑动质心 + 近期向量分流（不依赖 Embedder，便于单测）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence, runtime_checkable

import numpy as np

from core.logger import logger

DEFAULT_SIMILARITY_THRESHOLD = 0.55
MIN_TEXT_LEN_FOR_TOPIC = 2
RECENT_EMBEDDING_MAX = 5
DEFAULT_EMA_OLD = 0.8
DEFAULT_EMA_NEW = 0.2
DEFAULT_SIM_RECENT_MIN = 0.75
DEFAULT_SIM_LAST_MIN = 0.6


@dataclass(frozen=True)
class TopicRecord:
    """群内一条话题及其滑动向量与近期消息向量。"""

    id: int
    group_id: int
    centroid: np.ndarray  # shape (dim,), float64, L2 归一化（滑动 embedding）
    message_count: int
    anchor_preview: str
    recent_embeddings: tuple[np.ndarray, ...] = ()  # 时间正序，最多 RECENT_EMBEDDING_MAX 条


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
        msg_embedding_blob: bytes | None = None,
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


def should_create_new_topic(
    msg_vec: np.ndarray,
    topic: TopicRecord,
    *,
    sim_recent_min: float = DEFAULT_SIM_RECENT_MIN,
    sim_last_min: float = DEFAULT_SIM_LAST_MIN,
) -> bool:
    """在已通过滑动向量 centroid 门槛后，依据近期消息向量判断是否应新开 topic。"""
    recent = topic.recent_embeddings
    if not recent:
        return False
    d = np.asarray(msg_vec, dtype=np.float64).ravel()
    tail = recent[-RECENT_EMBEDDING_MAX:]
    sims = [float(np.dot(d, v)) for v in tail]
    max_sim = max(sims)
    if max_sim < float(sim_recent_min):
        return True
    last_vec = recent[-1]
    if float(np.dot(d, last_vec)) < float(sim_last_min):
        return True
    return False


class GroupTopicSegmenter:
    """对单条已向量化的文本，归入已有 topic 或新建 topic。"""

    def __init__(
        self,
        store: TopicSegmenterStore,
        *,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        max_preview_len: int = 500,
        ema_weight_old: float = DEFAULT_EMA_OLD,
        ema_weight_new: float = DEFAULT_EMA_NEW,
        sim_recent_min: float = DEFAULT_SIM_RECENT_MIN,
        sim_last_min: float = DEFAULT_SIM_LAST_MIN,
        recent_embedding_max: int = RECENT_EMBEDDING_MAX,
    ) -> None:
        self._store = store
        self._threshold = float(similarity_threshold)
        self._max_preview = int(max_preview_len)
        self._ema_old = float(ema_weight_old)
        self._ema_new = float(ema_weight_new)
        self._sim_recent_min = float(sim_recent_min)
        self._sim_last_min = float(sim_last_min)
        self._recent_max = int(recent_embedding_max)

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
        msg_blob = embedding_to_f32_blob(emb)

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

        split_new = False
        if best_record is not None and best_sim >= self._threshold:
            split_new = should_create_new_topic(
                emb,
                best_record,
                sim_recent_min=self._sim_recent_min,
                sim_last_min=self._sim_last_min,
            )

        recent_n = len(best_record.recent_embeddings) if best_record else 0
        logger.debug(
            "[group_topic_embed] group=%s user=%s msg_id=%s dim=%s centroid_th=%.3f | vs_topics: %s | best_topic=%s best_sim=%.4f recent_n=%s should_split=%s preview=%r",
            group_id,
            user_id,
            message_id,
            int(emb.shape[0]),
            self._threshold,
            sims_fmt,
            best_id if best_id is not None else "-",
            best_sim,
            recent_n,
            split_new,
            preview[:120],
        )

        if not topics or best_record is None or best_sim < self._threshold or split_new:
            tid = self._store.insert_topic(
                int(group_id),
                msg_blob,
                1,
                preview,
                created_at,
                created_at,
            )
            sim_out = 1.0 if best_record is None else float(best_sim)
            self._store.insert_message_assignment(
                tid,
                int(group_id),
                int(message_id),
                int(user_id),
                preview,
                None if best_record is None else float(best_sim),
                created_at,
                msg_embedding_blob=msg_blob,
            )
            return AssignmentResult(
                topic_id=tid,
                is_new_topic=True,
                similarity=sim_out,
                text_preview=preview,
            )

        assert best_record is not None and best_id is not None
        merged = _normalize(self._ema_old * best_record.centroid + self._ema_new * emb)
        new_count = int(best_record.message_count) + 1
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
            msg_embedding_blob=msg_blob,
        )
        return AssignmentResult(
            topic_id=int(best_id),
            is_new_topic=False,
            similarity=float(best_sim),
            text_preview=preview,
        )
