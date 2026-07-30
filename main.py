import time
import threading
import json as json_

from datetime import datetime
from core import api
from core.logger import logger
import core.context as runtime_context
import plugins # 一定要导入，否则不能正常读取插件
runtime_context.migrate_group_plugin_config()

import websocket  # pyright: ignore[reportMissingImports]

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


def plugin_pool(context: dict, event_type: str):
    group_id = context.get("group_id")
    for plugin_cls in runtime_context.plugin_registry:
        if event_type != "meta" and not runtime_context.is_plugin_enabled(plugin_cls, group_id):
            continue
        # 录制期间跳过非跑团功能包插件
        if group_id is not None and runtime_context.is_group_recording(group_id):
            if not runtime_context.is_plugin_allowed_during_recording(
                runtime_context.plugin_key(plugin_cls)
            ):
                continue
        plugin = plugin_cls(context)
        try:
            if plugin.match(event_type):
                plugin.handle()
        except Exception:
            logger.exception("插件 %s 处理失败", plugin_cls.__name__)


def on_message(_, message):
    context = enrich_context(json_.loads(message))
    # https://github.com/botuniverse/onebot-11/blob/master/event/README.md
    if "echo" in context:
        logger.debug("调用返回 -> " + message)
        # 响应报文通过队列传递给调用 API 的函数
        api.echo.match(context)
    else:
        event_type = resolve_event_type(context)
        if event_type == "meta":
            logger.debug("心跳事件 -> " + message)
        else:
            logger.info("收到事件 -> \n" + json_.dumps(message, indent=2, ensure_ascii=False))
        t = threading.Thread(target=plugin_pool, args=(context, event_type))
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
