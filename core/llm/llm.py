"""纯粹的 LLM 调用模块：输入请求，输出响应。

设计原则：
1) 不保存任何会话状态，不维护上下文。
2) 不拼接 Prompt，不注入 system 提示词。
3) 不做总结或后处理，只做参数透传和结果解析。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Sequence

from openai import OpenAI

DEFAULT_API_BASE = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TEMPERATURE = 1.0
DEFAULT_TOP_P = 1.0
DEFAULT_MAX_TOKENS = 1024


@dataclass(slots=True)
class Message:
    """单条对话消息。

    - role: 消息角色（如 system/user/assistant/tool）
    - content: 消息文本内容
    - name: 可选，通常用于 function calling 场景标注函数名
    """

    RoleType = Literal["system", "user", "assistant", "tool"]

    role: RoleType
    content: str
    name: Optional[str] = None


@dataclass(slots=True)
class GenerationConfig:
    """模型生成配置。"""

    # 目标模型名称，例如 deepseek-chat
    model: str = DEFAULT_MODEL
    # 温度：越高越发散，越低越稳定
    temperature: float = DEFAULT_TEMPERATURE
    # nucleus sampling 参数
    top_p: float = DEFAULT_TOP_P
    # 本次生成允许消耗的最大输出 token 数
    max_tokens: int = DEFAULT_MAX_TOKENS


@dataclass(slots=True)
class ToolSpec:
    """用于描述单个 function 的工具定义。

    - name: 函数名称
    - description: 函数用途描述
    - parameters: JSON Schema 风格参数定义
    """

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(slots=True)
class ToolCall:
    """用于描述模型发起的一次 function 调用。

    - name: 被调用函数名
    - arguments: 调用参数列表（按顺序展开）
    """

    name: str
    arguments: list[Any] = field(default_factory=list)


@dataclass(slots=True)
class ChatRequest:
    """聊天请求体。

    - messages: 标准消息列表（调用方负责组织上下文）
    - config: 本次调用的生成参数
    - tools: function calling 的工具定义列表（可选）
    """

    messages: Sequence[Message]
    config: GenerationConfig = field(default_factory=GenerationConfig)
    tools: Optional[Sequence[ToolSpec]] = None


@dataclass(slots=True)
class Usage:
    """本次调用的 token 消耗统计。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(slots=True)
class ChatResponse:
    """聊天响应体。

    - message: 模型返回的纯文本
    - finish_reason: 结束原因（如 stop/length/tool_calls 等）
    - usage: token 使用量
    """

    message: str
    finish_reason: str
    usage: Usage
    tool_calls: list[ToolCall] = field(default_factory=list)


def _api_key_from_env() -> Optional[str]:
    """从环境变量读取 API Key，并做空白清洗。"""
    raw = os.getenv("DEEPSEEK_API_KEY")
    if raw is None:
        return None
    key = str(raw).strip()
    return key or None


class LLM:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        # 优先使用显式传入的 api_key，其次从环境变量读取。
        key = api_key or _api_key_from_env()
        if not key:
            raise ValueError("Missing DeepSeek API key: set DEEPSEEK_API_KEY or pass api_key=")
        # 模块级只负责建立客户端，不持有任何对话历史。
        self.client = OpenAI(api_key=key, base_url=base_url or DEFAULT_API_BASE)

    def chat(self, request: ChatRequest) -> ChatResponse:
        """执行一次聊天调用：ChatRequest -> ChatResponse。"""

        # 将内部 Message 结构转换为 OpenAI SDK 所需字典格式。
        payload_messages: list[dict[str, Any]] = []
        for msg in request.messages:
            payload: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.name:
                payload["name"] = msg.name
            payload_messages.append(payload)

        # 仅做参数映射，不改写调用方传入的语义。
        params: dict[str, Any] = {
            "model": request.config.model,
            "messages": payload_messages,
            "temperature": request.config.temperature,
            "top_p": request.config.top_p,
            "max_tokens": request.config.max_tokens,
            "stream": False,
        }
        # tools 只在有值时透传，避免发送空字段。
        if request.tools:
            params["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in request.tools
            ]

        response = self.client.chat.completions.create(**params)
        choice = response.choices[0]
        content = choice.message.content or ""
        usage = response.usage
        tool_calls: list[ToolCall] = []
        for tool_call in getattr(choice.message, "tool_calls", None) or []:
            args_raw = getattr(getattr(tool_call, "function", None), "arguments", "") or ""
            args_list: list[Any] = []
            if isinstance(args_raw, str) and args_raw.strip():
                try:
                    parsed = json.loads(args_raw)
                    if isinstance(parsed, list):
                        args_list = parsed
                    elif isinstance(parsed, dict):
                        args_list = [parsed]
                    else:
                        args_list = [parsed]
                except Exception:
                    # 如果不是合法 JSON，保底按原始字符串返回。
                    args_list = [args_raw]

            tool_calls.append(
                ToolCall(
                    name=getattr(getattr(tool_call, "function", None), "name", "") or "",
                    arguments=args_list,
                )
            )

        # 解析为统一响应结构，便于上层模块稳定消费。
        return ChatResponse(
            message=content.strip(),
            finish_reason=choice.finish_reason or "unknown",
            usage=Usage(
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                total_tokens=getattr(usage, "total_tokens", 0) or 0,
            ),
            tool_calls=tool_calls,
        )


def chat_assistant_reply(user_text: str) -> str:
    """兼容旧调用入口：单条用户输入 -> 纯文本输出。

    注意：该函数不注入系统提示词，不维护历史，仅做最薄封装。
    """
    from core.llm.chat_facade import CompletionContext, complete

    outcome = complete(CompletionContext(messages=[Message(role="user", content=user_text)]))
    return outcome.message
