"""LLM 传输层协议：与具体 SDK 实现解耦，便于单测注入 Fake。"""

from __future__ import annotations

from typing import Protocol

from core.llm.llm import ChatRequest, ChatResponse


class LLMTransport(Protocol):
    """一次 chat completions 调用，签名与 `LLM.chat` 一致。"""

    def chat(self, request: ChatRequest) -> ChatResponse:
        ...
