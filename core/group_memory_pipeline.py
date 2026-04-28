from collections import defaultdict
import json
import os
from pathlib import Path
from threading import Lock
from typing import DefaultDict

from core import context as runtime_context
from core.logger import logger
from core.llm.llm import ChatRequest, GenerationConfig, LLM, Message

MEMORY_BATCH_SIZE = 40
MEMORY_CONTEXT_SIZE = 50
MEMORY_LLM_MODEL = "Qwen/Qwen3-8B"
MEMORY_PROMPT_PATH = (
    Path(__file__).resolve().parent / "llm" / "prompts" / "memory_point_gen_prompt.md"
)
MEMORY_LLM_BASE_URL = "https://api.siliconflow.cn/v1"
MEMORY_MAX_RETRIES = 3

_group_message_counter: DefaultDict[int, int] = defaultdict(int)
_counter_lock = Lock()


def _load_memory_prompt() -> str:
    return MEMORY_PROMPT_PATH.read_text(encoding="utf-8").strip()


def _build_chat_plain_text(records: list[dict]) -> str:
    lines = [runtime_context.format_chat_record(record) for record in records]
    return "\n".join(line for line in lines if line).strip()


def extract_group_memory_points(group_id: int, records: list[dict]) -> list[dict]:
    """提取群聊记忆点，返回解析后的 JSON 数组。"""
    if not records:
        return []

    api_key = os.getenv("SIFLOW_API_KEY", "").strip()
    if not api_key:
        logger.warning("群聊记忆提取跳过：缺少环境变量 SIFLOW_API_KEY。")
        return []

    try:
        prompt_prefix = _load_memory_prompt()
    except Exception as exc:
        logger.error("群 %s 记忆提取失败：读取 prompt 文件异常：%s", group_id, exc)
        return []
    chat_text = _build_chat_plain_text(records)
    if not chat_text:
        return []

    prompt = f"{prompt_prefix}\n\n{chat_text}"
    logger.info("群 %s 记忆提取 prompt:\n%s", group_id, prompt)
    llm = LLM(api_key=api_key, base_url=MEMORY_LLM_BASE_URL)
    messages = [Message(role="user", content=prompt)]
    config = GenerationConfig(
        model=MEMORY_LLM_MODEL,
        max_tokens=2048,
    )

    last_text = ""
    for attempt in range(1, MEMORY_MAX_RETRIES + 1):
        try:
            response = llm.chat(ChatRequest(messages=messages, config=config))
        except Exception as exc:
            logger.warning(
                "群 %s 记忆提取调用失败，准备重试（%s/%s）：%s",
                group_id,
                attempt,
                MEMORY_MAX_RETRIES,
                exc,
            )
            continue
        last_text = response.message.strip()
        logger.info("群 %s 记忆提取结果(第%s次):\n%s", group_id, attempt, last_text)
        try:
            parsed = json.loads(last_text)
            if isinstance(parsed, list):
                return parsed
            logger.warning("群 %s 记忆提取返回非数组 JSON，准备重试（%s/%s）。", group_id, attempt, MEMORY_MAX_RETRIES)
        except json.JSONDecodeError:
            logger.warning("群 %s 记忆提取 JSON 解析失败，准备重试（%s/%s）。", group_id, attempt, MEMORY_MAX_RETRIES)

    logger.error("群 %s 记忆提取失败：超过重试次数。最后返回：%s", group_id, last_text)
    return []


def after_plugins(context: dict) -> None:
    """
    插件执行后调用：
    - 仅处理群聊 message 事件
    - 每累计 40 条消息触发一次回调
    - 回调入参为：该群最新 50 条消息
    """
    if context.get("post_type") != "message":
        return
    if context.get("message_type") != "group":
        return

    group_id = context.get("group_id")
    if group_id is None:
        return
    gid = int(group_id)

    should_trigger = False
    with _counter_lock:
        _group_message_counter[gid] += 1
        if _group_message_counter[gid] % MEMORY_BATCH_SIZE == 0:
            should_trigger = True

    if should_trigger:
        payload = runtime_context.get_recent_chat_records(gid, limit=MEMORY_CONTEXT_SIZE)
        extract_group_memory_points(gid, payload)
