"""PromptBuilder: 组装给 LLM 的消息输入。

该模块负责将不同来源的信息（短期记忆、历史摘要、人设、长期记忆、当前问题）
拼装为标准 `Message` 列表，供 `LLM.chat()` 使用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from core.llm.llm import Message, ToolSpec


@dataclass(slots=True)
class Summary:
    """历史摘要条目。"""

    content: str
    source: str = ""


@dataclass(slots=True)
class Persona:
    """人设信息。"""

    name: str
    description: str
    style: str = ""


@dataclass(slots=True)
class Memory:
    """长期记忆条目。"""

    content: str
    score: float = 0.0
    source: str = ""


@dataclass(slots=True)
class PromptRequest:
    """Prompt 构建请求。"""

    # 当前用户输入（必须）
    query: str
    # 最近对话（短期记忆）
    recent_messages: list[Message] = field(default_factory=list)
    # 历史摘要（可多条）
    summaries: list[Summary] = field(default_factory=list)
    # 人设信息
    persona: Persona | None = None
    # 检索到的长期记忆
    relevant_memories: list[Memory] = field(default_factory=list)
    # 可用工具
    tools: list[ToolSpec] | None = None
    # 额外上下文（群聊 ID、用户 ID 等）
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PromptResult:
    """Prompt 构建结果。"""

    # 给 LLM Client 的最终输入
    messages: list[Message]
    # 估算 token（用于上层调控）
    used_tokens_estimate: int
    # 可选调试信息
    debug_info: Optional[dict[str, Any]] = None


class PromptBuilder:
    """将多源上下文拼装成最终 messages。"""

    def build(self, request: PromptRequest) -> PromptResult:
        """核心接口：build(request) -> PromptResult。"""
        query = request.query.strip()
        if not query:
            raise ValueError("PromptRequest.query is required")

        messages: list[Message] = []

        # 1) 人设信息优先放在前面，作为高优先级 system 指令。
        persona_msg = self._build_persona_message(request.persona)
        if persona_msg is not None:
            messages.append(persona_msg)

        # 2) 历史摘要，用于压缩长历史并保留关键事实。
        summary_msg = self._build_summary_message(request.summaries)
        if summary_msg is not None:
            messages.append(summary_msg)

        # 3) 长期记忆（检索召回结果）。
        memory_msg = self._build_memory_message(request.relevant_memories)
        if memory_msg is not None:
            messages.append(memory_msg)

        # 4) 最近消息直接拼接，保持对话连续性。
        messages.extend(request.recent_messages)

        # 5) 当前用户 query 作为本轮最终输入。
        messages.append(Message(role="user", content=query))

        token_estimate = self._estimate_tokens(messages)
        debug_info = {
            "meta": request.meta,
            "summary_count": len(request.summaries),
            "memory_count": len(request.relevant_memories),
            "recent_message_count": len(request.recent_messages),
            "tool_count": len(request.tools or []),
            "final_message_count": len(messages),
        }

        return PromptResult(
            messages=messages,
            used_tokens_estimate=token_estimate,
            debug_info=debug_info,
        )

    def _build_persona_message(self, persona: Persona | None) -> Message | None:
        if persona is None:
            return None

        lines = [
            "你的人设信息如下，请在后续回答中保持一致：",
            f"- 名称: {persona.name}",
            f"- 描述: {persona.description}",
        ]
        if persona.style:
            lines.append(f"- 风格: {persona.style}")

        return Message(role="system", content="\n".join(lines), name="persona")

    def _build_summary_message(self, summaries: list[Summary]) -> Message | None:
        if not summaries:
            return None

        lines = ["以下是历史摘要，请优先参考："]
        for idx, item in enumerate(summaries, start=1):
            source = f"（来源: {item.source}）" if item.source else ""
            lines.append(f"{idx}. {item.content}{source}")

        return Message(role="system", content="\n".join(lines), name="history_summaries")

    def _build_memory_message(self, memories: list[Memory]) -> Message | None:
        if not memories:
            return None

        lines = ["以下是检索到的长期记忆，可在相关时引用："]
        for idx, item in enumerate(memories, start=1):
            extra = []
            if item.score:
                extra.append(f"score={item.score:.4f}")
            if item.source:
                extra.append(f"source={item.source}")
            suffix = f" ({', '.join(extra)})" if extra else ""
            lines.append(f"{idx}. {item.content}{suffix}")

        return Message(role="system", content="\n".join(lines), name="relevant_memories")

    def _estimate_tokens(self, messages: list[Message]) -> int:
        """粗略估算 token 数，用于上层预算控制。

        这里采用保守的启发式估算，不追求与模型计费完全一致：
        - 文本长度 / 2 作为基础 token 估算；
        - 每条消息额外加 4 token 作为结构开销。
        """
        content_chars = sum(len(msg.content) for msg in messages)
        return content_chars // 2 + len(messages) * 4
