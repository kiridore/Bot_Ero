"""独立事件线程、通知失败隔离和启用状态快照。"""
import ast
from pathlib import Path
from types import SimpleNamespace

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, get_ident

from core.logger import logger
from core.message_output import MessageOutput
from core.plugin_dispatch import Operation, Subscription


def test_thread_main_entry_uses_snapshot_and_flushes_once():
    # main 导入会启动监控面板；只编译实际入口函数，测试不启动网络服务。
    tree = ast.parse(Path("main.py").read_text(encoding="utf-8"))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "plugin_pool")
    settings = {"first": True, "second": True}
    sent = []
    seen = []
    thread = get_ident()

    class First:
        __module__ = "plugins.first"

        def __init__(self, raw):
            self.op = raw["_operation"]

        def match(self, event_type):
            return True

        def handle(self):
            settings["second"] = False
            self.op.output.submit("甲", merge="reply")
            seen.append(get_ident())

    class Second(First):
        __module__ = "plugins.second"

        def handle(self):
            self.op.output.submit("乙", merge="reply")
            seen.append(get_ident())

    runtime = SimpleNamespace(
        DEFAULT_GROUP_ID=None, plugin_registry=[First, Second],
        plugin_key=lambda cls: cls.__module__.split(".")[1],
        plugin_settings_snapshot=lambda *args: settings,
        register_gate=lambda *a: None,
        should_remind_register=lambda *a: False,
        is_group_recording=lambda gid: False,
    )
    namespace = {"runtime_context": runtime, "Operation": Operation, "MessageOutput": MessageOutput,
                 "send_request": lambda request: sent.append(request) or 1, "logger": logger}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "main.py", "exec"), namespace)
    namespace["plugin_pool"]({"group_id": 1, "user_id": 2}, "message")
    assert seen == [thread, thread]
    assert [r.content for r in sent] == ["甲\n乙"]
    seen.clear()
    namespace["plugin_pool"]({"group_id": 1, "user_id": 2}, "message")
    assert seen == [thread]


def test_thread_isolation_and_child_notifications():
    barrier = Barrier(2)

    def run(name):
        thread = get_ident()
        seen = []
        sent = []
        output = MessageOutput(lambda request: sent.append((get_ident(), request)) or 1, ("private", 1))

        def first(op, data):
            seen.append(get_ident())
            barrier.wait(timeout=5)
            op.publish("second", data)

        def second(op, data):
            seen.append(get_ident())
            op.output.submit(data["name"], merge="same")

        op = Operation({"p": True}, output, subscriptions=[
            Subscription("first", "p", first), Subscription("second", "p", second),
        ])
        op.publish("first", {"name": name})
        op.finish()
        assert seen == [thread, thread]
        assert sent[0][0] == thread
        assert sent[0][1].content == name
        return thread

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, name) for name in ("甲", "乙")]
        assert len({f.result() for f in futures}) == 2


def test_failure_discards_output_and_child_but_continues(caplog):
    sent = []
    output = MessageOutput(lambda r: sent.append(r) or 1, ("group", 1))

    def bad(op, data):
        op.output.submit("错误成功提示")
        op.publish("child", {})
        raise ValueError("不得发给用户的内部细节")

    def good(op, data):
        assert data == {"ok": 1}
        op.output.submit("正常结果")

    def child(op, data):
        raise AssertionError("失败的处理函数不应该产生子通知")

    op = Operation({"p": True}, output, subscriptions=[
        Subscription("start", "p", bad), Subscription("start", "p", good),
        Subscription("child", "p", child),
    ])
    op.publish("start", {"ok": 1})
    op.finish()
    assert op.failures == ["p"]
    assert [r.content for r in sent] == ["正常结果", "p 处理失败，其他已完成的操作不受影响。"]
    assert "内部细节" in caplog.text


def test_snapshot_cleanup_and_payload_isolation():
    enabled = {"on": True, "off": False}
    seen = []
    output = MessageOutput(lambda r: 1)

    def mutate(op, data):
        data["nested"].append(2)
        seen.append("mutate")

    def inspect(op, data):
        assert data["nested"] == [1]
        seen.append("cleanup")

    op = Operation(enabled, output, subscriptions=[
        Subscription("start", "on", mutate),
        Subscription("start", "off", lambda *args: seen.append("wrong")),
        Subscription("start", "off", inspect, cleanup=True),
    ])
    enabled["on"] = False
    data = {"nested": [1]}
    op.publish("start", data)
    data["nested"].append(3)
    op.finish()
    assert seen == ["mutate", "cleanup"]


def test_failure_cycle_with_changing_source_is_bounded():
    output = MessageOutput(lambda r: 1)
    def repeat(op, payload):
        op.publish("repeat", {"source_operation": str(int(payload["source_operation"]) + 1)})
    op = Operation({"p": True}, output, subscriptions=[Subscription("repeat", "p", repeat)])
    op.MAX_NOTIFICATIONS = 5
    op.publish("repeat", {"source_operation": "0"})
    op.finish()
    assert op.failures == ["p"]
    assert op._published == 5


def test_failure_cycle_is_bounded():
    output = MessageOutput(lambda r: 1)
    op = Operation({"p": True}, output, subscriptions=[
        Subscription("a", "p", lambda op, _: op.publish("b", {})),
        Subscription("b", "p", lambda op, _: op.publish("a", {})),
    ])
    op.publish("a", {})
    op.finish()
    assert op.failures == ["p"]
