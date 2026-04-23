"""根据 topic 下消息预览调用 LLM 生成持久化摘要。"""

from __future__ import annotations

from datetime import datetime

from core.database_manager import DbManager
from core.logger import logger
from core.llm.client_protocol import LLMTransport
from core.llm.llm import ChatRequest, GenerationConfig, LLM, Message

DEFAULT_MIN_MESSAGES = 3
DEFAULT_EVERY_N = 5
DEFAULT_USER_PREVIEW_LIMIT = 30
DEFAULT_PROMPT_CHAR_CAP = 4000


def should_refresh_topic_summary(
    message_count: int,
    *,
    min_messages: int = DEFAULT_MIN_MESSAGES,
    every_n: int = DEFAULT_EVERY_N,
) -> bool:
    """是否在写入第 ``message_count`` 条归属消息后刷新摘要（首刷在 min_messages，之后每 every_n 条）。"""
    if message_count < int(min_messages):
        return False
    if message_count == int(min_messages):
        return True
    return message_count >= int(every_n) and message_count % int(every_n) == 0


_SYSTEM_PROMPT = (
    "你是群聊话题分析助手。下面编号行是同一话题下多条消息的简短预览（可能含占位符）。"
    "请用 1～3 句中文概括讨论主题，不要逐条复述，不要编造未出现的内容。"
)


class TopicSummaryService:
    def __init__(
        self,
        llm: LLMTransport | None = None,
        *,
        min_messages: int = DEFAULT_MIN_MESSAGES,
        preview_limit: int = DEFAULT_USER_PREVIEW_LIMIT,
        prompt_char_cap: int = DEFAULT_PROMPT_CHAR_CAP,
        generation: GenerationConfig | None = None,
    ) -> None:
        self._llm = llm or LLM()
        self._min_messages = int(min_messages)
        self._preview_limit = int(preview_limit)
        self._prompt_char_cap = int(prompt_char_cap)
        self._generation = generation or GenerationConfig(temperature=0.3, max_tokens=256, top_p=0.9)

    def refresh_topic_summary(self, topic_id: int, *, db: DbManager) -> None:
        previews = db.list_topic_message_previews(int(topic_id), limit=self._preview_limit)
        if len(previews) < self._min_messages:
            return
        lines = [f"{i + 1}. {p}" for i, p in enumerate(previews) if (p or "").strip()]
        body = "\n".join(lines)
        if len(body) > self._prompt_char_cap:
            body = body[: self._prompt_char_cap - 20] + "\n…（已截断部分预览）"
        user_content = "消息预览：\n" + body
        try:
            resp = self._llm.chat(
                ChatRequest(
                    messages=[
                        Message(role="system", content=_SYSTEM_PROMPT),
                        Message(role="user", content=user_content),
                    ],
                    config=self._generation,
                )
            )
            summary = (resp.message or "").strip()
            if not summary:
                logger.warning("[topic_summary] LLM 返回空摘要 topic_id=%s", topic_id)
                return
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db.update_topic_summary(int(topic_id), summary, ts)
        except Exception as exc:
            logger.warning("[topic_summary] 生成失败 topic_id=%s: %s", topic_id, exc)
