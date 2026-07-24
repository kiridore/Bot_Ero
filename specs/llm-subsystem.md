# Spec: LLM 子系统

> 关联规范: [plugins.md](plugins.md) | [conventions.md](conventions.md) | [architecture.md](architecture.md)
> 父文档: [CLAUDE.md](../CLAUDE.md)
> 最后更新: 2026-06-29

---

## Constraint: 分层架构

LLM 子系统采用自底向上的分层设计，位于 `core/llm/`：

```
┌──────────────────────────────────────────────┐
│  plugin_tools.py    Plugin → ToolSpec 转换    │ ← 上层：连接 Plugin 系统
├──────────────────────────────────────────────┤
│  conversation_engine.py   对话状态机          │ ← 编排层
│  prompt_builder.py        提示词组装          │
├──────────────────────────────────────────────┤
│  chat_facade.py           单轮完成门面        │ ← 门面层
│  client_protocol.py       传输协议(Protocol)  │
├──────────────────────────────────────────────┤
│  llm.py                   OpenAI SDK 传输     │ ← 传输层
├──────────────────────────────────────────────┤
│  embedder.py              嵌入服务            │ ← 独立
└──────────────────────────────────────────────┘
```

每层职责单一，无循环依赖。上层可以替换下层实现。

---

## Constraint: 传输层 (`llm.py`)

**纯传输，无状态，无提示词拼接，无后处理。**

### 数据类

所有数据类使用 `@dataclass(slots=True)`：

| 类 | 用途 |
|----|------|
| `Message` | 单条消息：`role` (system/user/assistant/tool), `content`, `name` |
| `GenerationConfig` | 生成配置：`model`, `temperature`, `top_p`, `max_tokens` |
| `ToolSpec` | 工具定义：`name`, `description`, `parameters` (JSON Schema) |
| `ToolCall` | 工具调用：`name`, `arguments` |
| `ChatRequest` | 请求：`messages`, `config`, `tools` |
| `ChatResponse` | 响应：`message`, `finish_reason`, `usage`, `tool_calls` |
| `Usage` | Token 用量：`prompt_tokens`, `completion_tokens`, `total_tokens` |

### LLM 类

```python
class LLM:
    def __init__(self, api_key=None, base_url=None):
        # 创建 openai.OpenAI 客户端
        # api_key 默认从 DEEPSEEK_API_KEY 环境变量读取
        # base_url 默认 "https://api.deepseek.com"

    def chat(self, request: ChatRequest) -> ChatResponse:
        # 非流式请求，解析 tool_calls (JSON → ToolCall)
```

### 默认值

| 参数 | 默认值 |
|------|--------|
| `api_base` | `https://api.deepseek.com` |
| `model` | `deepseek-chat` |
| `temperature` | `1.0` |
| `top_p` | `1.0` |
| `max_tokens` | `1024` |

### 环境变量

- `DEEPSEEK_API_KEY` — DeepSeek API 密钥（必须）

---

## Constraint: 传输协议 (`client_protocol.py`)

```python
class LLMTransport(Protocol):
    def chat(self, request: ChatRequest) -> ChatResponse:
        ...
```

Protocol 类（结构子类型），用于依赖注入。`LLM` 类自动满足此协议。

---

## Constraint: 门面层 (`chat_facade.py`)

```python
@dataclass(slots=True)
class CompletionContext:
    messages: list[Message]
    tools: Sequence[ToolSpec] | None = None
    config: GenerationConfig | None = None
    meta: dict[str, Any]

@dataclass(slots=True)
class CompletionOutcome:
    message: str
    finish_reason: str
    usage: Usage
    tool_calls: list[ToolCall]
    raw: ChatResponse

def complete(context: CompletionContext, *, client: LLMTransport | None = None) -> CompletionOutcome:
    # 如果不提供 client，默认创建 LLM() 实例
```

---

## Constraint: 提示词构建器 (`prompt_builder.py`)

组装顺序：persona → summaries → memories → recent_messages → user_query

```python
class PromptBuilder:
    def build(self, request: PromptRequest) -> PromptResult:
        # 返回 assembled messages + token 估算

@dataclass(slots=True)
class PromptRequest:
    query: str
    recent_messages: list[Message]
    summaries: list[Summary]
    persona: Persona | None
    relevant_memories: list[Memory]
    tools: list[ToolSpec] | None
```

---

## Constraint: 对话引擎 (`conversation_engine.py`)

状态机编排单轮对话。**核心入口:** `ConversationEngine.handle_turn()`

### 状态机 (TurnState)

```
RECEIVED → CONTEXT_READY → DECIDED → PROMPT_READY
    → LLM_RESPONDED → TOOLS_EXECUTED
    → MEMORY_UPDATED → SUMMARY_UPDATED → PERSONA_UPDATED → FINISHED
```

### 输入/输出

```python
@dataclass
class TurnRequest:
    session_id: str
    user_id: str
    message: str
    metadata: dict | None

@dataclass
class TurnResult:
    reply: str
    tool_calls: list[ToolCall] | None
    events: list[EngineEvent]
```

### 扩展点（全部 Protocol 化，有 Noop 默认实现）

| 组件 | 职责 | 默认实现 |
|------|------|---------|
| `ContextProvider` | 获取对话上下文 | `DefaultContextProvider`（空） |
| `Policy` | 决策：是否总结/更新 persona | `DefaultPolicy`（消息>40字用总结） |
| `ToolExecutor` | 执行 LLM 请求的工具调用 | `NoopToolExecutor` |
| `MemoryStore` | 持久化对话轮次 | `NoopMemoryStore` |
| `PersonaStore` | 更新用户 persona | `NoopPersonaStore` |

### ConversationEngine 构造

```python
engine = ConversationEngine(
    llm=LLM(),                              # LLMTransport
    prompt_builder=PromptBuilder(),
    context_provider=MyContextProvider(),   # ContextProvider
    policy=MyPolicy(),                      # Policy
    tool_executor=MyToolExecutor(),         # ToolExecutor
    memory_store=MyMemoryStore(),           # MemoryStore
    persona_store=MyPersonaStore(),         # PersonaStore
)
```

---

## Constraint: Plugin → ToolSpec 转换 (`plugin_tools.py`)

将插件自动转为 LLM function calling 的 ToolSpec：

```python
def plugin_class_to_tool_spec(plugin_cls, *, parameters=None) -> ToolSpec:
    # 读取 plugin_cls.name 和 plugin_cls.description
    # 返回 ToolSpec(name=..., description=..., parameters=...)

def plugins_to_tool_specs(plugins, *, parameters=None, dedupe_by_name=True) -> list[ToolSpec]:
    # 批量转换，可按 name 去重
```

**MUST:** 插件的 `name` 和 `description` 必须非空，否则转换失败。

---

## Constraint: 嵌入服务 (`embedder.py`)

线程安全的嵌入向量服务单例。

```python
class Embedder:
    # 单例模式（double-checked locking）
    # API: SiliconFlow (https://api.siliconflow.cn)
    # 模型: BAAI/bge-m3
    # 输出: L2 归一化向量

    def embed(self, texts: str | list[str]) -> list[list[float]]:
        # 返回归一化向量列表
```

**环境变量:** `SIFLOW_API_KEY` — SiliconFlow API 密钥

---

## Constraint: 提示词文件

LLM 提示词模板位于 `core/llm/prompts/`:

| 文件 | 用途 |
|------|------|
| `router_prompt.md` | 意图分类：chat / function / unknown |
| `chat_prompt.md` | 小埃角色卡：16-20岁女高中生、二次元语气、波浪线、偶尔喵~ |
| `rp_prompt.md` | 角色扮演指导：第一人称内心独白在 `<think>` 标签中 |

**修改提示词时**：直接用 Markdown 编辑，保持 `<think>` 结构不变。

---

## Constraint: 当前开发状态

| 组件 | 状态 | 说明 |
|------|------|------|
| 传输层 (llm.py) | ✅ 完成 | DeepSeek 正常工作 |
| 门面 (chat_facade.py) | ✅ 完成 | |
| 提示词构建 (prompt_builder.py) | ✅ 完成 | 含 token 估算 |
| 对话引擎 (conversation_engine.py) | ✅ 框架完成 | 扩展点实现为 Noop |
| Plugin → ToolSpec (plugin_tools.py) | ✅ 完成 | |
| 嵌入 (embedder.py) | ✅ 完成 | |
| Memory 持久化 | ❌ 未实现 | NoopMemoryStore |
| Persona 持久化 | ❌ 未实现 | NoopPersonaStore |
| 工具执行器 | ❌ 未实现 | NoopToolExecutor |
| 上下文提供者 | ⚠️ 仅默认 | DefaultContextProvider 返回空 |

**扩展 LLM 功能时：**
1. 选择合适的扩展点（Protocol）实现具体逻辑
2. 传入 `ConversationEngine` 构造函数
3. 不要修改引擎核心逻辑
