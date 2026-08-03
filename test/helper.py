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


class MockApiWrapper:
    def __init__(self, raw_context: dict):
        self.context = Event(raw_context)
        self.sent_messages: list[tuple[str, tuple]] = []
        self.api_calls: list[tuple[str, dict]] = []

    def send_msg(self, *message) -> int:
        self.sent_messages.append(("send_msg", message))
        return 0

    def send_group_msg(self, *message) -> int:
        self.sent_messages.append(("send_group_msg", message))
        return 0

    def send_private_msg(self, *message) -> int:
        self.sent_messages.append(("send_private_msg", message))
        return 0

    def call_api(self, action: str, params: dict) -> dict:
        self.api_calls.append((action, params))
        if action in ("send_msg", "send_group_msg", "send_private_msg"):
            self.sent_messages.append((action, params["message"]))
        return {}


def make_group_message(text: str, user_id: int = 123456,
                       group_id: int = 296470819, nickname: str = "测试用户") -> dict:
    return {
        "post_type": "message",
        "message_type": "group",
        "user_id": user_id,
        "group_id": group_id,
        "message": [{"type": "text", "data": {"text": text}}],
        "sender": {"user_id": user_id, "nickname": nickname, "role": "member"},
        "time": 0,
        "message_id": -1,
    }


def make_private_message(text: str, user_id: int = 123456,
                         nickname: str = "测试用户") -> dict:
    return {
        "post_type": "message",
        "message_type": "private",
        "user_id": user_id,
        "message": [{"type": "text", "data": {"text": text}}],
        "sender": {"user_id": user_id, "nickname": nickname},
        "time": 0,
        "message_id": -1,
    }
