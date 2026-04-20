"""单次补全门面：已拼好的消息上下文 -> 模型结果。

扩展说明（记忆 / 画像）：
- 短期多轮上下文：在传入本门面的 `messages` 之前，由 `PromptBuilder` 与
  `ConversationContext.recent_messages` 组装。
- 长期记忆检索：在 `ContextProvider.get` 中填充 `relevant_memories`，经
  Prompt 组装进入 `messages`；写入由 `MemoryStore` 承担。
- 用户画像：通过 `Persona` 与 `PersonaStore` 在编排层维护，同样进入 Prompt。

本模块不参与上述逻辑，仅封装「messages + tools + config -> API -> 解析结果」。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from core.llm.client_protocol import LLMTransport
from core.llm.llm import (
    ChatRequest,
    ChatResponse,
    GenerationConfig,
    LLM,
    Message,
    ToolCall,
    ToolSpec,
    Usage,
)


@dataclass(slots=True)
class CompletionContext:
    """单次模型调用的输入边界。"""

    messages: list[Message]
    tools: Sequence[ToolSpec] | None = None
    config: GenerationConfig | None = None
    # 不参与 HTTP 参数；供日志、链路追踪或上层扩展读取。
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CompletionOutcome:
    """单次模型调用的输出边界。"""

    message: str
    finish_reason: str
    usage: Usage
    tool_calls: list[ToolCall]
    raw: ChatResponse


def complete(context: CompletionContext, *, client: LLMTransport | None = None) -> CompletionOutcome:
    """执行一次补全：`CompletionContext` -> `CompletionOutcome`。"""
    transport = client if client is not None else LLM()
    cfg = context.config if context.config is not None else GenerationConfig()
    response = transport.chat(
        ChatRequest(messages=context.messages, config=cfg, tools=context.tools),
    )
    return CompletionOutcome(
        message=response.message,
        finish_reason=response.finish_reason,
        usage=response.usage,
        tool_calls=response.tool_calls,
        raw=response,
    )
