"""无默认群部署（社区形态）的群发兜底：丢弃 + 告警；私有形态回落默认群不变。"""
import json
import sys
import unittest

import core.api as api
import core.context as runtime_context
from core.api import ApiWrapper
from core.cq import text


class _FakeWS:
    """记录发送帧并同步回注 echo 响应，解除 call_api 的 30s 队列阻塞。"""

    def __init__(self):
        self.frames = []

    def send(self, data):
        self.frames.append(data)
        payload = json.loads(data)
        api.echo.match({"echo": payload["echo"], "status": "ok", "data": {"message_id": 42}})


class TestSendFallback(unittest.TestCase):
    def setUp(self):
        api.echo = api.Echo()
        self.ws = _FakeWS()
        api.WS_APP = self.ws
        self.wrapper = ApiWrapper({})  # 裸上下文：无 group_id / user_id
        self._old_default = runtime_context.DEFAULT_GROUP_ID

    def tearDown(self):
        runtime_context.DEFAULT_GROUP_ID = self._old_default

    def test_drop_when_no_default_group(self):
        runtime_context.DEFAULT_GROUP_ID = None
        with self.assertLogs("core.logger", level="WARNING"):
            self.assertEqual(self.wrapper.send_group_msg(text("hi")), 0)
            self.assertEqual(self.wrapper.send_group_forward_msg([text("hi")]), 0)
            self.assertEqual(self.wrapper.send_group_forward_nodes([{"type": "node", "data": {}}]), 0)
        self.assertEqual(self.ws.frames, [])

    def test_fallback_to_default_group_when_configured(self):
        runtime_context.DEFAULT_GROUP_ID = 12345
        self.assertEqual(self.wrapper.send_group_msg(text("hi")), 42)
        self.assertEqual(len(self.ws.frames), 1)
        frame = json.loads(self.ws.frames[0])
        self.assertEqual(frame["action"], "send_group_msg")
        self.assertEqual(frame["params"]["group_id"], 12345)


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=2))
