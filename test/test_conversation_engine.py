from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.llm.conversation_engine import (  # noqa: E402
    ConversationContext,
    ConversationEngine,
    EngineEvent,
    PolicyDecision,
    TurnRequest,
    TurnState,
)
from core.llm.llm import ChatResponse, Message, ToolCall, ToolSpec, Usage  # noqa: E402
from core.llm.prompt_builder import Memory, Persona, Summary  # noqa: E402


class FakeContextProvider:
    def get(self, session_id: str, user_id: str, metadata=None) -> ConversationContext:
        return ConversationContext(
            recent_messages=[Message(role="assistant", content="你好，我还记得上次的话题。")],
            summaries=[Summary(content="用户上次咨询了插件配置。", source="s1")],
            persona=Persona(name="小埃", description="友好助手", style="简洁"),
            relevant_memories=[Memory(content="用户偏好中文回答。", score=0.98, source="m1")],
            tools=[
                ToolSpec(
                    name="search_docs",
                    description="搜索文档",
                    parameters={"type": "object", "properties": {"q": {"type": "string"}}},
                )
            ],
            metadata={"source": "unit_test"},
        )


class FakePolicy:
    def decide(self, context: ConversationContext, message: str) -> PolicyDecision:
        return PolicyDecision(use_summary=True, update_persona=True, allow_tool_call=True)


class FakeLLM:
    def chat(self, request):
        return ChatResponse(
            message="这是模型回复",
            finish_reason="tool_calls",
            usage=Usage(prompt_tokens=12, completion_tokens=8, total_tokens=20),
            tool_calls=[ToolCall(name="search_docs", arguments=[{"q": "插件配置"}])],
        )


class FakeToolExecutor:
    def __init__(self):
        self.called = False

    def execute(self, tool_calls, *, context, request):
        self.called = True
        return {"executed_count": len(tool_calls), "ok": True}


class FakeMemoryStore:
    def __init__(self):
        self.append_called = False
        self.summary_called = False

    def append(self, request, response, *, context):
        self.append_called = True

    def update_summary(self, *, session_id, user_id, context, response):
        self.summary_called = True


class FakePersonaStore:
    def __init__(self):
        self.called = False

    def update(self, *, session_id, user_id, context, response):
        self.called = True


class TestConversationEngine(unittest.TestCase):
    def test_handle_turn_should_run_full_pipeline(self):
        tool_executor = FakeToolExecutor()
        memory_store = FakeMemoryStore()
        persona_store = FakePersonaStore()

        engine = ConversationEngine(
            llm=FakeLLM(),
            context_provider=FakeContextProvider(),
            policy=FakePolicy(),
            tool_executor=tool_executor,
            memory_store=memory_store,
            persona_store=persona_store,
        )

        result = engine.handle_turn(
            TurnRequest(
                session_id="group_1001",
                user_id="u_42",
                message="帮我查一下插件配置",
                metadata={"scene": "group"},
            )
        )

        self.assertEqual(result.reply, "这是模型回复")
        self.assertIsNotNone(result.tool_calls)
        self.assertEqual(result.tool_calls[0].name, "search_docs")
        self.assertTrue(tool_executor.called)
        self.assertTrue(memory_store.append_called)
        self.assertTrue(memory_store.summary_called)
        self.assertTrue(persona_store.called)

        event_types = [e.event_type for e in result.events]
        self.assertIn(TurnState.RECEIVED.value, event_types)
        self.assertIn(TurnState.CONTEXT_READY.value, event_types)
        self.assertIn(TurnState.DECIDED.value, event_types)
        self.assertIn(TurnState.PROMPT_READY.value, event_types)
        self.assertIn(TurnState.LLM_RESPONDED.value, event_types)
        self.assertIn(TurnState.TOOLS_EXECUTED.value, event_types)
        self.assertIn(TurnState.MEMORY_UPDATED.value, event_types)
        self.assertIn(TurnState.SUMMARY_UPDATED.value, event_types)
        self.assertIn(TurnState.PERSONA_UPDATED.value, event_types)
        self.assertEqual(result.events[-1].event_type, TurnState.FINISHED.value)

    def test_handle_turn_should_require_non_empty_message(self):
        engine = ConversationEngine(llm=FakeLLM())
        with self.assertRaises(ValueError):
            engine.handle_turn(TurnRequest(session_id="s", user_id="u", message="   "))


if __name__ == "__main__":
    unittest.main(verbosity=2)
