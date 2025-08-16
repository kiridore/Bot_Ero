import time
import threading
import json as json_

from datetime import datetime
from core.logger import logger
from core.base import Plugin
from plugins import *
import core.context as context

import websocket

import core.base as base

# WS_URL = "ws://192.168.0.103:3001"   # 本机调试用
WS_URL = "ws://127.0.0.1:3001"   # WebSocket 地址


def plugin_pool(context: dict):
    # 遍历所有的 Plugin 的子类，执行匹配
    for P in Plugin.__subclasses__():
        plugin = P(context)
        if plugin.match():
            plugin.handle()


def on_message(_, message):
    # https://github.com/botuniverse/onebot-11/blob/master/event/README.md
    context = json_.loads(message)
    if "echo" in context:
        logger.debug("调用返回 -> " + message)
        # 响应报文通过队列传递给调用 API 的函数
        base.echo.match(context)
    elif "meta_event_type" in context:
        logger.debug("心跳事件 -> " + message)
    else:
        logger.info("收到事件 -> " + message)
        # 消息事件，开启线程
        global only_to_me_flag
        only_to_me_flag = False
        t = threading.Thread(target=plugin_pool, args=(context, ))
        t.start()


if __name__ == "__main__":
    base.echo = base.Echo()
    base.WS_APP = websocket.WebSocketApp(
        WS_URL,
        on_message=on_message,
        on_open=lambda _: logger.debug("连接成功......"),
        on_close=lambda _: logger.debug("重连中......"),
    )

    while True:  # 掉线重连
        # 数据储存
        logger.info("数据库启动")
        context.script_start_time = datetime.now()
        base.WS_APP.run_forever()

        time.sleep(5)

