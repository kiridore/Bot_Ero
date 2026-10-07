"""任务2.3：真实发送适配器与旧插件共存，失败不重跑业务、不重复发送。"""
import ast
from pathlib import Path
from unittest.mock import Mock

import pytest

from core import api, config, context
from core.base import Plugin
from core.cq import text
from core.logger import logger
from core.message_output import MessageOutput, send_request
from core.plugin_dispatch import Operation

ROOT = Path(__file__).resolve().parents[1]


def load_pool():
    # 不 import main：它在导入时启动监控面板。编译实际函数测试真实分发路径。
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "plugin_pool")
    namespace = {"runtime_context": context, "Operation": Operation, "MessageOutput": MessageOutput,
                 "send_request": send_request, "logger": logger}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "main.py", "exec"), namespace)
    return namespace["plugin_pool"]


@pytest.fixture
def transport(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "messages.db")
    monkeypatch.setattr(api, "WS_APP", Mock(), raising=False)
    monkeypatch.setattr(context, "is_group_recording", lambda gid: False)
    calls = []

    def send(self, action, params):
        calls.append((action, params))
        return {"status": "ok", "data": {"message_id": len(calls)}}

    monkeypatch.setattr(api.ApiWrapper, "call_api", send)
    return calls


def test_legacy_and_migrated_plugins_send_exactly_once(transport, monkeypatch):
    class Legacy(Plugin):
        __module__ = "plugins.legacy_test"

        def match(self, event_type):
            return True

        def handle(self):
            self.api.send_msg(text("旧插件"))

    class Migrated(Legacy):
        __module__ = "plugins.migrated_test"

        def handle(self):
            self.submit_message(text("新插件第一段"), merge="reply")
            self.submit_message(text("新插件第二段"), merge="reply")

    monkeypatch.setattr(context, "plugin_registry", [Legacy, Migrated])
    monkeypatch.setattr(context, "plugin_settings_snapshot", lambda *args: {
        "legacy_test": True, "migrated_test": True,
    })
    load_pool()({"group_id": 10, "user_id": 42, "message": [], "post_type": "message"}, "message")
    assert [action for action, _ in transport] == ["send_group_msg", "send_group_msg"]
    assert [params["message"][0]["data"]["text"] for _, params in transport] == [
        "旧插件", "新插件第一段\n新插件第二段",
    ]
    assert all(params["group_id"] == 10 for _, params in transport)


@pytest.mark.parametrize("kind,content,action", [
    ("text", "普通文本", "send_private_msg"),
    ("segments", [text("消息段")], "send_private_msg"),
    ("forward", [text("转发正文")], "send_private_forward_msg"),
    ("nodes", [{"type": "node", "data": {"id": "1"}}], "send_private_forward_msg"),
])
def test_transport_routes_each_format_once(transport, kind, content, action):
    output = MessageOutput(send_request, ("private", 42))
    operation = Operation({}, output)
    output.submit(content, kind=kind)
    operation.finish()
    operation.finish()
    assert len(transport) == 1
    assert transport[0][0] == action
    assert transport[0][1]["user_id"] == 42
    assert "group_id" not in transport[0][1]


def test_send_exception_keeps_committed_business_and_logs_operation(transport, monkeypatch, caplog):
    writes = []
    sends = []

    def fail(self, action, params):
        sends.append(params)
        raise TimeoutError("内部网络细节")

    monkeypatch.setattr(api.ApiWrapper, "call_api", fail)
    output = MessageOutput(send_request, ("private", 42))
    operation = Operation({}, output, operation_id="test-send-failure")

    def business():
        writes.append("业务已完成")
        output.submit("业务成功")

    assert operation.execute("checkin", business)
    operation.finish()
    operation.finish()
    assert writes == ["业务已完成"]
    assert len(sends) == 1
    assert "test-send-failure" in caplog.text
    assert "分段=1" in caplog.text
    assert "private" in caplog.text and "42" in caplog.text
    assert "不自动重试" in caplog.text


def test_business_failure_drops_success_output_without_leaking_exception(transport):
    output = MessageOutput(send_request, ("private", 42))
    operation = Operation({}, output)

    def fail():
        output.submit("错误成功提示")
        raise RuntimeError("secret-token-in-internal-error")

    assert not operation.execute("weekly_quest", fail)
    assert operation.execute("checkin", lambda: output.submit("打卡已保存"))
    operation.finish()
    assert len(transport) == 2
    bodies = [params["message"][0]["data"]["text"] for _, params in transport]
    assert bodies == ["打卡已保存", "weekly_quest 处理失败，其他已完成的操作不受影响。"]
    assert all("secret-token" not in body and "错误成功提示" not in body for body in bodies)


def test_migrated_sources_do_not_keep_legacy_send_calls():
    files = ["checkin/__init__.py", "checkin_recall/__init__.py", "roll_back/__init__.py",
             "weekly_quest/events.py", "title/events.py", "redeem_shop/events.py"]
    for relative in files:
        path = ROOT / "plugins" / relative
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert not node.func.attr.startswith("send_"), (relative, node.lineno)
                assert node.func.attr != "call_api", (relative, node.lineno)


def test_output_cannot_be_shared_between_operations():
    output = MessageOutput(lambda request: 1, ("private", 42))
    Operation({}, output)
    with pytest.raises(ValueError, match="不能共用"):
        Operation({}, output)
