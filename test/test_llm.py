"""`core.llm.llm` 的独立测试脚本。

运行方式：
`python test/test_llm.py`

注意：
该脚本会真实调用 LLM API，请确保已配置 `DEEPSEEK_API_KEY`，
并注意接口消耗与网络连通性。
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

from openai import AuthenticationError


# 确保直接执行脚本时可以导入项目根目录下的模块。
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.llm.llm import (  # noqa: E402
    ChatRequest,
    GenerationConfig,
    LLM,
    Message,
    ToolSpec,
    chat_assistant_reply,
)


class TestLLM(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.getenv("DEEPSEEK_API_KEY", "").strip():
            raise unittest.SkipTest("未配置 DEEPSEEK_API_KEY，跳过真实 API 测试")

        cls.llm = LLM()

    def _chat_or_fail(self, request: ChatRequest):
        """执行真实调用，并在认证失败时给出更清晰的错误信息。"""
        try:
            return self.llm.chat(request)
        except AuthenticationError as exc:
            self.fail(f"LLM 认证失败，请检查 DEEPSEEK_API_KEY 是否有效: {exc}")

    def test_chat_should_return_structured_response(self):
        request = ChatRequest(
            messages=[
                Message(role="system", content="你是测试助手，只输出一句简短中文问候。"),
                Message(role="user", content="请回复一句不超过10个字的问候语。"),
            ],
            config=GenerationConfig(
                temperature=0.1,
                top_p=0.8,
                max_tokens=64,
            ),
        )

        response = self._chat_or_fail(request)

        self.assertIsInstance(response.message, str)
        self.assertTrue(bool(response.message.strip()))
        self.assertIsInstance(response.finish_reason, str)
        self.assertTrue(bool(response.finish_reason.strip()))
        self.assertGreaterEqual(response.usage.prompt_tokens, 0)
        self.assertGreaterEqual(response.usage.completion_tokens, 0)
        self.assertGreaterEqual(response.usage.total_tokens, 0)
        self.assertIsInstance(response.tool_calls, list)

    def test_chat_should_support_tool_calling(self):
        request = ChatRequest(
            messages=[
                Message(
                    role="user",
                    content=(
                        "你必须调用 `search_docs` 工具来完成任务，不要直接回答。"
                        "参数 keyword 请填写 `BotEro`。"
                    ),
                )
            ],
            config=GenerationConfig(
                temperature=0.0,
                top_p=1.0,
                max_tokens=128,
            ),
            tools=[
                ToolSpec(
                    name="search_docs",
                    description="搜索项目文档",
                    parameters={
                        "type": "object",
                        "properties": {
                            "keyword": {"type": "string"},
                        },
                        "required": ["keyword"],
                    },
                )
            ],
        )

        response = self._chat_or_fail(request)

        self.assertIsInstance(response.tool_calls, list)
        self.assertGreaterEqual(len(response.tool_calls), 1)
        self.assertEqual(response.tool_calls[0].name, "search_docs")
        self.assertIsInstance(response.tool_calls[0].arguments, list)
        self.assertGreaterEqual(len(response.tool_calls[0].arguments), 1)

    def test_chat_assistant_reply_should_return_plain_message(self):
        request = ChatRequest(
            messages=[Message(role="user", content="请回复“测试成功”四个字")],
            config=GenerationConfig(
                temperature=0.1,
                top_p=0.8,
                max_tokens=32,
            ),
        )
        response = self._chat_or_fail(request)
        result = response.message

        self.assertIsInstance(result, str)
        self.assertTrue(bool(result.strip()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
