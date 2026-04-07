import time
import threading
import json as json_

from datetime import datetime
from core import api
from core.logger import logger
from core.base import Plugin
from plugins import *
import core.context as context

import websocket

import core.base as base

# WS_URL = "ws://192.168.0.103:3001"   # 本机调试用
WS_URL = "ws://127.0.0.1:3001"   # WebSocket 地址
token = 123456
DEFAULT_GROUP_ID = 296470819 # 在这里填写你想固定使用的群号


def enrich_context(raw_context: dict) -> dict:
    # 使用固定默认群号，便于私聊等场景下复用群能力
    raw_context["default_group_id"] = DEFAULT_GROUP_ID
    return raw_context


def _all_plugin_classes(base_cls):
    classes = []
    for sub in base_cls.__subclasses__():
        classes.append(sub)
        classes.extend(_all_plugin_classes(sub))
    return classes


def plugin_pool(context: dict, event_type: str):
    # 递归遍历所有 Plugin 子类（包含二级继承）
    for P in _all_plugin_classes(Plugin):
        plugin = P(context)
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
        # 数据储存
        logger.info("数据库启动")
        context.script_start_time = datetime.now()
        api.WS_APP.run_forever()

        if context.should_shutdown:
            break

        time.sleep(5)

