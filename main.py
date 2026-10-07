import time
import threading
import json as json_

from datetime import datetime
from core import api
from core.config import WS_URL, WS_TOKEN
from core.logger import logger
import core.context as runtime_context
import plugins # 一定要导入，否则不能正常读取插件

from core.web_panel import start_panel
from core.plugin_dispatch import Operation
from core.message_output import MessageOutput, send_request

start_panel()

import websocket  # pyright: ignore[reportMissingImports]


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
    user_id = context.get("user_id")
    target = (("group", group_id) if group_id is not None else
              ("private", user_id) if user_id is not None else
              ("group", runtime_context.DEFAULT_GROUP_ID) if runtime_context.DEFAULT_GROUP_ID else None)
    try:
        settings = runtime_context.plugin_settings_snapshot(group_id, user_id)
    except Exception:
        logger.exception("读取插件设置失败，本次事件不执行，防止绕过关闭设置")
        return
    operation = Operation(settings, MessageOutput(send_request, target))
    logger.debug("操作 %s 开始：类型=%s 消息=%s 群=%s 用户=%s",
                 operation.id, event_type, context.get("message_id"), group_id, user_id)
    context = dict(context, _operation=operation)
    for plugin_cls in tuple(runtime_context.plugin_registry):
        if event_type != "meta" and not operation.is_enabled(runtime_context.plugin_key(plugin_cls)):
            continue
        # 录制期间跳过非跑团功能包插件
        if group_id is not None and runtime_context.is_group_recording(group_id):
            if not runtime_context.is_plugin_allowed_during_recording(
                runtime_context.plugin_key(plugin_cls)
            ):
                continue
        def handle(cls=plugin_cls):
            plugin = cls(context)
            if plugin.match(event_type):
                plugin.handle()
        operation.execute(runtime_context.plugin_key(plugin_cls), handle)
        operation.drain()
    operation.finish()


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
    from core.config import BOTERO_VERSION
    logger.info("BotEro v%s 启动（WS: %s）", BOTERO_VERSION, WS_URL)
    api.echo = api.Echo()
    api.WS_APP = websocket.WebSocketApp(
        WS_URL,
        header=[f"Authorization: Bearer {WS_TOKEN}"],
        on_message=on_message,
        on_open=lambda _: logger.debug("连接成功......"),
    )

    while True:  # 掉线重连
        runtime_context.script_start_time = datetime.now()
        api.WS_APP.run_forever()
        time.sleep(5)
