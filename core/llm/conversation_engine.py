"""Conversation Engine：状态机 + 调度器 + 决策中心。

职责：
- 接收一次用户输入（turn request）
- 编排上下文读取、决策、prompt 构建、LLM 调用、工具执行、副作用写入
- 返回一次系统响应（turn result）及完整副作用事件列表
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from core.llm.llm import ChatRequest, ChatResponse, LLM, Message, ToolCall, ToolSpec
from core.llm.prompt_builder import Memory, Persona, PromptBuilder, PromptRequest, Summary


@dataclass(slots=True)
class TurnRequest:
    """Conversation Engine 单轮输入。"""

    session_id: str
    user_id: str
    message: str
    metadata: dict[str, Any] | None = None


@dataclass(slots=True)
class EngineEvent:
    """引擎副作用事件。"""

    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TurnResult:
    """Conversation Engine 单轮输出。"""

    reply: str
    tool_calls: list[ToolCall] | None
    events: list[EngineEvent]


@dataclass(slots=True)
class ConversationContext:
    """本轮决策与提示词构建依赖的上下文。"""

    recent_messages: list[Message] = field(default_factory=list)
    summaries: list[Summary] = field(default_factory=list)
    persona: Persona | None = None
    relevant_memories: list[Memory] = field(default_factory=list)
    tools: list[ToolSpec] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PolicyDecision:
    """决策中心输出。"""

    use_summary: bool = False
    update_persona: bool = False
    allow_tool_call: bool = True


class TurnState(str, Enum):
    """单轮处理状态机。"""

    RECEIVED = "received"
    CONTEXT_READY = "context_ready"
    DECIDED = "decided"
    PROMPT_READY = "prompt_ready"
    LLM_RESPONDED = "llm_responded"
    TOOLS_EXECUTED = "tools_executed"
    MEMORY_UPDATED = "memory_updated"
    SUMMARY_UPDATED = "summary_updated"
    PERSONA_UPDATED = "persona_updated"
    FINISHED = "finished"


class ContextProvider(Protocol):
    def get(self, session_id: str, user_id: str, metadata: dict[str, Any] | None = None) -> ConversationContext:
        ...


class Policy(Protocol):
    def decide(self, context: ConversationContext, message: str) -> PolicyDecision:
        ...


class ToolExecutor(Protocol):
    def execute(self, tool_calls: list[ToolCall], *, context: ConversationContext, request: TurnRequest) -> dict[str, Any]:
        ...


class MemoryStore(Protocol):
    def append(self, request: TurnRequest, response: ChatResponse, *, context: ConversationContext) -> None:
        ...

    def update_summary(self, *, session_id: str, user_id: str, context: ConversationContext, response: ChatResponse) -> None:
        ...


class PersonaStore(Protocol):
    def update(self, *, session_id: str, user_id: str, context: ConversationContext, response: ChatResponse) -> None:
        ...


class DefaultContextProvider:
    """默认上下文提供器：返回空上下文。"""

    def get(self, session_id: str, user_id: str, metadata: dict[str, Any] | None = None) -> ConversationContext:
        return ConversationContext(metadata=dict(metadata or {}))


class DefaultPolicy:
    """默认策略：短消息不开 summary，检测自我描述时允许更新 persona。"""

    def decide(self, context: ConversationContext, message: str) -> PolicyDecision:
        text = (message or "").strip()
        return PolicyDecision(
            use_summary=len(text) > 40,
            update_persona=("我是" in text or "我叫" in text),
            allow_tool_call=True,
        )


class NoopToolExecutor:
    """默认工具执行器：不做真实执行，仅返回空结果。"""

    def execute(self, tool_calls: list[ToolCall], *, context: ConversationContext, request: TurnRequest) -> dict[str, Any]:
        return {"executed_count": len(tool_calls)}


class NoopMemoryStore:
    """默认记忆存储器：无副作用。"""

    def append(self, request: TurnRequest, response: ChatResponse, *, context: ConversationContext) -> None:
        return None

    def update_summary(self, *, session_id: str, user_id: str, context: ConversationContext, response: ChatResponse) -> None:
        return None


class NoopPersonaStore:
    """默认人设存储器：无副作用。"""

    def update(self, *, session_id: str, user_id: str, context: ConversationContext, response: ChatResponse) -> None:
        return None


class ConversationEngine:
    """Conversation Engine 主实现。"""

    def __init__(
        self,
        *,
        llm: LLM,
        prompt_builder: PromptBuilder | None = None,
        context_provider: ContextProvider | None = None,
        policy: Policy | None = None,
        tool_executor: ToolExecutor | None = None,
        memory_store: MemoryStore | None = None,
        persona_store: PersonaStore | None = None,
    ):
        self.llm = llm
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.context_provider = context_provider or DefaultContextProvider()
        self.policy = policy or DefaultPolicy()
        self.tool_executor = tool_executor or NoopToolExecutor()
        self.memory_store = memory_store or NoopMemoryStore()
        self.persona_store = persona_store or NoopPersonaStore()

    def handle_turn(self, request: TurnRequest) -> TurnResult:
        """主入口：接收一次输入，产出一次响应及副作用记录。"""
        message = (request.message or "").strip()
        if not message:
            raise ValueError("TurnRequest.message is required")

        events: list[EngineEvent] = [EngineEvent(event_type=TurnState.RECEIVED.value, payload={"session_id": request.session_id})]

        # 1) 获取上下文
        context = self.context_provider.get(
            request.session_id,
            request.user_id,
            metadata=request.metadata,
        )
        events.append(
            EngineEvent(
                event_type=TurnState.CONTEXT_READY.value,
                payload={
                    "recent_messages": len(context.recent_messages),
                    "summaries": len(context.summaries),
                    "relevant_memories": len(context.relevant_memories),
                    "tools": len(context.tools or []),
                },
            )
        )

        # 2) 决策
        decision = self.policy.decide(context, message)
        events.append(
            EngineEvent(
                event_type=TurnState.DECIDED.value,
                payload={
                    "use_summary": decision.use_summary,
                    "update_persona": decision.update_persona,
                    "allow_tool_call": decision.allow_tool_call,
                },
            )
        )

        # 3) 构建 prompt
        prompt_result = self.prompt_builder.build(
            PromptRequest(
                query=message,
                recent_messages=context.recent_messages,
                summaries=context.summaries,
                persona=context.persona,
                relevant_memories=context.relevant_memories,
                tools=context.tools if decision.allow_tool_call else None,
                meta={
                    "session_id": request.session_id,
                    "user_id": request.user_id,
                    **dict(context.metadata or {}),
                    **dict(request.metadata or {}),
                    "policy": {
                        "use_summary": decision.use_summary,
                        "update_persona": decision.update_persona,
                        "allow_tool_call": decision.allow_tool_call,
                    },
                },
            )
        )
        events.append(
            EngineEvent(
                event_type=TurnState.PROMPT_READY.value,
                payload={
                    "message_count": len(prompt_result.messages),
                    "used_tokens_estimate": prompt_result.used_tokens_estimate,
                },
            )
        )

        # 4) 调用 LLM
        response = self.llm.chat(
            ChatRequest(
                messages=prompt_result.messages,
                tools=context.tools if decision.allow_tool_call else None,
            )
        )
        events.append(
            EngineEvent(
                event_type=TurnState.LLM_RESPONDED.value,
                payload={
                    "finish_reason": response.finish_reason,
                    "tool_call_count": len(response.tool_calls),
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    },
                },
            )
        )

        # 5) 工具调用（可选）
        if response.tool_calls:
            tool_result = self.tool_executor.execute(
                response.tool_calls,
                context=context,
                request=request,
            )
            events.append(
                EngineEvent(
                    event_type=TurnState.TOOLS_EXECUTED.value,
                    payload=tool_result,
                )
            )

        # 6) 写入 memory
        self.memory_store.append(request, response, context=context)
        events.append(EngineEvent(event_type=TurnState.MEMORY_UPDATED.value))

        # 7) 触发 summary（按需）
        if decision.use_summary:
            self.memory_store.update_summary(
                session_id=request.session_id,
                user_id=request.user_id,
                context=context,
                response=response,
            )
            events.append(EngineEvent(event_type=TurnState.SUMMARY_UPDATED.value))

        # 8) 更新 persona（按需）
        if decision.update_persona:
            self.persona_store.update(
                session_id=request.session_id,
                user_id=request.user_id,
                context=context,
                response=response,
            )
            events.append(EngineEvent(event_type=TurnState.PERSONA_UPDATED.value))

        events.append(EngineEvent(event_type=TurnState.FINISHED.value))
        return TurnResult(
            reply=response.message,
            tool_calls=response.tool_calls or None,
            events=events,
        )
