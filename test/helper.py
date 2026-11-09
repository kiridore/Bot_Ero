from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 让 Plugin.__init__ 不崩溃（main.py 才会初始化这些全局变量）
import core.api as _api
_api.WS_APP = None  # type: ignore[attr-defined]
_api.echo = _api.Echo()  # type: ignore[attr-defined]

from core.event import Event
from core.cq import forward


class MockApiWrapper:
    def __init__(self, raw_context: dict):
        self.context = Event(raw_context)
        self.sent_messages: list[tuple[str, tuple]] = []
        self.api_calls: list[tuple[str, dict]] = []
        self.deleted_messages: list[int] = []
        self.delete_msg_ok = True

    def send_msg(self, *message) -> int:
        self.sent_messages.append(("send_msg", message))
        return 0

    def send_group_msg(self, *message) -> int:
        self.sent_messages.append(("send_group_msg", message))
        return 0

    def send_private_msg(self, *message) -> int:
        self.sent_messages.append(("send_private_msg", message))
        return 0

    def send_forward_msg(self, message: list) -> int:
        if self.context.group_id is not None:
            return self.send_group_forward_msg(message)
        return self.send_private_forward_msg(message)

    def send_group_forward_msg(self, message: list) -> int:
        self.call_api("send_group_forward_msg", {"group_id": self.context.group_id, "messages": forward(message)})
        return 0

    def send_private_forward_msg(self, message: list) -> int:
        self.call_api("send_private_forward_msg", {"user_id": self.context.user_id, "messages": forward(message)})
        return 0

    def send_forward_nodes(self, nodes: list) -> int:
        if self.context.group_id is not None:
            return self.send_group_forward_nodes(nodes)
        return self.send_private_forward_nodes(nodes)

    def send_group_forward_nodes(self, nodes: list) -> int:
        self.call_api("send_group_forward_msg", {"group_id": self.context.group_id, "messages": nodes})
        return 0

    def send_private_forward_nodes(self, nodes: list) -> int:
        self.call_api("send_private_forward_msg", {"user_id": self.context.user_id, "messages": nodes})
        return 0

    def delete_msg(self, message_id: int) -> bool:
        self.api_calls.append(("delete_msg", {"message_id": int(message_id)}))
        self.deleted_messages.append(int(message_id))
        return self.delete_msg_ok

    def call_api(self, action: str, params: dict) -> dict:
        self.api_calls.append((action, params))
        if action in ("send_msg", "send_group_msg", "send_private_msg"):
            self.sent_messages.append((action, params["message"]))
        return {}


def make_group_message(text: str, user_id: int = 123456,
                       group_id: int = 296470819, nickname: str = "测试用户",
                       message_id: int = -1) -> dict:
    return {
        "post_type": "message",
        "message_type": "group",
        "user_id": user_id,
        "group_id": group_id,
        "message": [{"type": "text", "data": {"text": text}}],
        "sender": {"user_id": user_id, "nickname": nickname, "role": "member"},
        "time": 0,
        "message_id": message_id,
    }


def make_private_message(text: str, user_id: int = 123456,
                         nickname: str = "测试用户",
                         message_id: int = -1) -> dict:
    return {
        "post_type": "message",
        "message_type": "private",
        "user_id": user_id,
        "message": [{"type": "text", "data": {"text": text}}],
        "sender": {"user_id": user_id, "nickname": nickname},
        "time": 0,
        "message_id": message_id,
    }


class RecordingOutput:
    """测试替身：提交立即落到底层 API，保持既有 sent_messages 断言可读。"""

    operation_id = None
    suppressed = False

    def __init__(self, api):
        self.api = api

    def submit(self, content, *, target=None, kind="text", merge=None, order=0, node=None):
        from core.cq import text as _text

        if kind == "text":
            return self.api.send_msg(_text(content))
        if kind == "segments":
            if target is None:
                return self.api.send_msg(*content)
            scope, target_id = target
            # 显式目标对应迁移前的 call_api 调用，保留 api_calls 断言可见性
            if scope == "group":
                return self.api.call_api("send_group_msg",
                                         {"group_id": int(target_id), "message": list(content)})
            return self.api.call_api("send_private_msg",
                                     {"user_id": int(target_id), "message": list(content)})
        if kind == "forward":
            return self.api.send_forward_msg(content)
        return self.api.send_forward_nodes(content)

    def failure(self, plugin):
        pass

    def flush(self):
        pass


def bind_output(plugin):
    """给直接构造的插件绑定输出替身与操作上下文，返回 operation。

    若调用方已设置 operation（例如带黑名单快照），保留其快照。
    """
    from types import SimpleNamespace

    existing = getattr(plugin, 'operation', None)
    snapshot = getattr(existing, 'blacklist_snapshot', None) if existing is not None else None
    operation = SimpleNamespace(output=RecordingOutput(plugin.api), blacklist_snapshot=snapshot)
    plugin.operation = operation
    return operation
