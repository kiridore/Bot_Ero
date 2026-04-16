import time
import threading
import json as json_

from datetime import datetime
from core import api
from core.logger import logger
from plugins import *
import core.context as runtime_context

import websocket

# WS_URL = "ws://192.168.0.103:3001"   # 本机调试用
WS_URL = "ws://127.0.0.1:3001"   # WebSocket 地址
token = 123456
DEFAULT_GROUP_ID = 296470819 # 在这里填写你想固定使用的群号


def enrich_context(raw_context: dict) -> dict:
    # 使用固定默认群号，便于私聊等场景下复用群能力
    raw_context["default_group_id"] = DEFAULT_GROUP_ID
    return raw_context


def plugin_pool(context: dict, event_type: str):
    for plugin_cls in runtime_context.plugin_registry:
        plugin = plugin_cls(context)
        if plugin.match(event_type):
            plugin.handle()

def on_message(_, message):
    # https://github.com/botuniverse/onebot-11/blob/master/event/README.md
    context = enrich_context(json_.loads(message))
    if "echo" in context:
        logger.debug("调用返回 -> " + message)
        # 响应报文通过队列传递给调用 API 的函数
        api.echo.match(context)
    elif "meta_event_type" in context:
        logger.debug("心跳事件 -> " + message)
        t = threading.Thread(target=plugin_pool, args=(context, "meta"))
        t.start()
    else:
        logger.info("收到事件 -> " + message)
        pool_event = "message"
        if context.get("post_type") == "notice":
            pool_event = "notice"
        t = threading.Thread(target=plugin_pool, args=(context, pool_event))
        t.start()


if __name__ == "__main__":
    api.echo = api.Echo()
    api.WS_APP = websocket.WebSocketApp(
        WS_URL,
        header=[f"Authorization: Bearer {token}"],
        on_message=on_message,
        on_open=lambda _: logger.debug("连接成功......"),
        on_close=lambda _: logger.debug("重连中......"),  # pyright: ignore[reportArgumentType]
    )

    while True:  # 掉线重连
        context.script_start_time = datetime.now()
        api.WS_APP.run_forever()

        if context.should_shutdown:
            break

        time.sleep(5)

