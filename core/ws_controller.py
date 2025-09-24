import websocket

import queue
import json as json_
import threading
import collections
from core.logger import logger
from core.manager import PlugManager, plugin_manager_inst

class Echo:
    def __init__(self):
        self.echo_num = 0
        self.echo_list = collections.deque(maxlen=20)

    def get(self):
        self.echo_num += 1
        q = queue.Queue(maxsize=1)
        self.echo_list.append((self.echo_num, q))
        return self.echo_num, q

    def match(self, context: dict):
        for obj in self.echo_list:
            if context["echo"] == obj[0]:
                obj[1].put(context)

echo : Echo
WS_APP : websocket.WebSocketApp
WS_URL = "ws://192.168.0.103:3001"   # 本机调试用
# WS_URL = "ws://127.0.0.1:3001"   # WebSocket 地址

def on_message(_, message):
    # https://github.com/botuniverse/onebot-11/blob/master/event/README.md
    context = json_.loads(message)
    if "echo" in context:
        logger.debug("调用返回 -> " + message)
        # 响应报文通过队列传递给调用 API 的函数
        echo.match(context)
    elif "meta_event_type" in context:
        logger.debug("心跳事件 -> " + message)
    else:
        logger.info("收到事件 -> " + message)
        # 消息事件，开启线程
        global only_to_me_flag
        only_to_me_flag = False
        t = threading.Thread(target=PlugManager.parse, args=(plugin_manager_inst, context, ))
        t.start()

def init():
    global echo, WS_APP
    echo = Echo()
    WS_APP = websocket.WebSocketApp(
        WS_URL,
        on_message=on_message,
        on_open=lambda _: logger.debug("连接成功......"),
        on_close=lambda _: logger.debug("重连中......"),
    )

def call_api(action: str, params: dict) -> dict:
    echo_num, q = echo.get()
    data = json_.dumps({"action": action, "params": params, "echo": echo_num})
    logger.info("发送调用 <- " + data)
    WS_APP.send(data)
    try:    # 阻塞至响应或者等待30s超时
        return q.get(timeout=30)
    except queue.Empty:
        logger.error("API调用[{echo_num}] 超时......")
        return {}
