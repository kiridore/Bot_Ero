"""群聊话题划分：正文扁平化 + 向量 + 划分入库。"""

from __future__ import annotations

from datetime import datetime

import numpy as np

from core.database_manager import DbManager
from core.group_message_text import flatten_group_message_content, group_message_has_user_text
from core.group_topic_segmenter import AssignmentResult, GroupTopicSegmenter, TopicSegmenterStore
from core.group_topic_summary import TopicSummaryService, should_refresh_topic_summary
from core.llm.embedder import Embedder


def _now_sql() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class GroupTopicService:
    def __init__(
        self,
        *,
        embedder: Embedder,
        store: TopicSegmenterStore,
        similarity_threshold: float = 0.55,
        min_text_len: int = 2,
        dbmanager: DbManager | None = None,
        summary_service: TopicSummaryService | None = None,
        summary_min_messages: int = 3,
        summary_every_n: int = 5,
    ) -> None:
        self._embedder = embedder
        self._min_len = int(min_text_len)
        self._segmenter = GroupTopicSegmenter(store, similarity_threshold=similarity_threshold)
        self._dbmanager = dbmanager
        self._summary_min = int(summary_min_messages)
        self._summary_every_n = int(summary_every_n)
        self._summary = summary_service if summary_service is not None else (
            TopicSummaryService() if dbmanager is not None else None
        )

    @classmethod
    def from_db_manager(cls, dbmanager: DbManager) -> GroupTopicService:
        return cls(
            embedder=Embedder(),
            store=dbmanager.group_topic_store(),
            dbmanager=dbmanager,
        )

    def on_group_message(
        self,
        group_id: int,
        user_id: int,
        message_id: int,
        message_segments: list | tuple | str | None,
    ) -> AssignmentResult | None:
        if not group_message_has_user_text(message_segments, int(group_id)):
            return None
        text = flatten_group_message_content(message_segments, int(group_id)).strip()
        if len(text) < self._min_len:
            return None
        raw_vec = self._embedder.embed([text])
        emb = np.asarray(raw_vec[0], dtype=np.float64).ravel()
        n = float(np.linalg.norm(emb))
        if n > 0.0:
            emb = emb / n
        ts = _now_sql()
        result = self._segmenter.assign_topic(
            int(group_id),
            text,
            emb,
            message_id=int(message_id),
            user_id=int(user_id),
            created_at=ts,
        )
        if (
            self._summary
            and self._dbmanager
            and should_refresh_topic_summary(
                result.message_count_after,
                min_messages=self._summary_min,
                every_n=self._summary_every_n,
            )
        ):
            self._summary.refresh_topic_summary(result.topic_id, db=self._dbmanager)
        return result
