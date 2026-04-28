import time
import threading
import json as json_
from typing import Any

from datetime import datetime
from core import api
from core.logger import logger
import core.context as runtime_context
from core import group_memory_pipeline
import plugins # 一定要导入，否则不能正常读取插件

import websocket

# WS_URL = "ws://192.168.0.103:3001"   # 本机调试用
WS_URL = "ws://127.0.0.1:3001"   # WebSocket 地址
token = 123456


# 往获取到的context中插入额外的信息
def enrich_context(raw_context: dict) -> dict:
    return raw_context


def resolve_event_type(context: dict) -> str:
    if "meta_event_type" in context:
        return "meta"
    if context.get("post_type") == "notice":
        return "notice"
    return "message"


def extract_plain_text(message_segments: Any) -> str:
    if not isinstance(message_segments, list):
        return ""
    parts: list[str] = []
    for seg in message_segments:
        if not isinstance(seg, dict):
            continue
        if seg.get("type") != "text":
            continue
        data = seg.get("data", {})
        if isinstance(data, dict):
            parts.append(str(data.get("text", "")))
    return "".join(parts).strip()


def collect_recent_chat_records(context: dict):
    if context.get("post_type") != "message":
        return
    if context.get("message_type") != "group":
        return
    group_id = context.get("group_id")
    if group_id is None:
        return
    record = {
        "time": context.get("time"),
        "message_id": context.get("message_id"),
        "group_id": group_id,
        "user_id": context.get("user_id"),
        "message_type": context.get("message_type"),
        "nickname": (context.get("sender") or {}).get("nickname"),
        "plain_text": extract_plain_text(context.get("message")),
    }
    runtime_context.recent_chat_records[int(group_id)].append(record)


def identify_plugins(context: dict, event_type: str):
    matched_plugins = []
    for plugin_cls in runtime_context.plugin_registry:
        plugin = plugin_cls(context)
        if plugin.match(event_type):
            matched_plugins.append(plugin)
    return matched_plugins


def execute_plugins(matched_plugins):
    for plugin in matched_plugins:
        plugin.handle()


def process_event(context: dict, event_type: str):
    matched_plugins = identify_plugins(context, event_type)
    execute_plugins(matched_plugins)
    group_memory_pipeline.after_plugins(context)

def on_message(_, message):
    context = enrich_context(json_.loads(message))
    # https://github.com/botuniverse/onebot-11/blob/master/event/README.md
    if "echo" in context:
        logger.debug("调用返回 -> " + message)
        # 响应报文通过队列传递给调用 API 的函数
        api.echo.match(context)
    else:
        event_type = resolve_event_type(context)
        collect_recent_chat_records(context)
        if event_type == "meta":
            logger.debug("心跳事件 -> " + message)
        else:
            logger.info("收到事件 -> " + message)
        t = threading.Thread(target=process_event, args=(context, event_type))
        t.start()


if __name__ == "__main__":
    api.echo = api.Echo()
    api.WS_APP = websocket.WebSocketApp(
        WS_URL,
        header=[f"Authorization: Bearer {token}"],
        on_message=on_message,
        on_open=lambda _: logger.debug("连接成功......"),
    )

    while True:  # 掉线重连
        runtime_context.script_start_time = datetime.now()
        api.WS_APP.run_forever()
        time.sleep(5)

