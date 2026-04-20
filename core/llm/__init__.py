"""QQ 机器人 LLM 子系统公开入口。

分层：
- `core.llm.llm`：纯传输（OpenAI 兼容 API），无会话状态。
- `core.llm.chat_facade`：单次补全的显式输入输出（messages -> outcome）。
- `core.llm.prompt_builder`：将摘要、记忆、人设等拼成 messages。
- `core.llm.conversation_engine`：单轮编排（上下文、策略、Prompt、补全、工具、副作用）。

记忆与用户画像扩展：在编排层实现 `ContextProvider`（读上下文含 `relevant_memories`）、
`MemoryStore`（写入与摘要）、`PersonaStore`（人设更新）；门面层不负责检索逻辑。

子模块路径（如 `from core.llm.llm import LLM`）保持稳定，本包同时提供聚合导出。
"""

from __future__ import annotations

from core.llm.chat_facade import CompletionContext, CompletionOutcome, complete
from core.llm.client_protocol import LLMTransport
from core.llm.conversation_engine import (
    ConversationContext,
    ConversationEngine,
    ContextProvider,
    DefaultContextProvider,
    DefaultPolicy,
    EngineEvent,
    MemoryStore,
    NoopMemoryStore,
    NoopPersonaStore,
    NoopToolExecutor,
    PersonaStore,
    Policy,
    PolicyDecision,
    ToolExecutor,
    TurnRequest,
    TurnResult,
    TurnState,
)
from core.llm.llm import (
    DEFAULT_API_BASE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    ChatRequest,
    ChatResponse,
    GenerationConfig,
    LLM,
    Message,
    ToolCall,
    ToolSpec,
    Usage,
    chat_assistant_reply,
)
from core.llm.plugin_tools import (
    DEFAULT_PLUGIN_TOOL_PARAMETERS,
    plugin_class_to_tool_spec,
    plugins_to_tool_specs,
)
from core.llm.prompt_builder import Memory, Persona, PromptBuilder, PromptRequest, PromptResult, Summary

__all__ = [
    "DEFAULT_API_BASE",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_MODEL",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_TOP_P",
    "DEFAULT_PLUGIN_TOOL_PARAMETERS",
    "ChatRequest",
    "ChatResponse",
    "CompletionContext",
    "CompletionOutcome",
    "ConversationContext",
    "ConversationEngine",
    "ContextProvider",
    "DefaultContextProvider",
    "DefaultPolicy",
    "EngineEvent",
    "GenerationConfig",
    "LLM",
    "LLMTransport",
    "Memory",
    "MemoryStore",
    "Message",
    "NoopMemoryStore",
    "NoopPersonaStore",
    "NoopToolExecutor",
    "Persona",
    "PersonaStore",
    "Policy",
    "PolicyDecision",
    "PromptBuilder",
    "PromptRequest",
    "PromptResult",
    "Summary",
    "ToolCall",
    "ToolExecutor",
    "ToolSpec",
    "TurnRequest",
    "TurnResult",
    "TurnState",
    "Usage",
    "chat_assistant_reply",
    "complete",
    "plugin_class_to_tool_spec",
    "plugins_to_tool_specs",
]
