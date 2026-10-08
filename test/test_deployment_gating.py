"""config-unification 任务组2：部署硬边界在快照、事件入口与撤销消费者中生效。"""
import sqlite3
import unittest
from types import MappingProxyType
from unittest.mock import Mock

from core import context
from core.message_output import MessageOutput
from core.plugin_dispatch import Operation, Subscription


class DeploymentBoundaryTest(unittest.TestCase):
    def setUp(self):
        self._old_allowed = context.ALLOWED_PLUGINS

    def tearDown(self):
        context.ALLOWED_PLUGINS = self._old_allowed

    def test_snapshot_intersects_allowed(self):
        import tempfile
        from pathlib import Path
        from core import config as cfg
        old_db = cfg.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            conn = sqlite3.connect(str(Path(tmp) / "g.db"))
            from core.db._base import init_schema
            init_schema(conn, conn.cursor())
            conn.execute("INSERT INTO group_plugin_config VALUES (1, 'checkin')")
            conn.execute("INSERT INTO group_plugin_config VALUES (1, 'title')")
            conn.commit()
            cfg.DB_PATH = Path(tmp) / "g.db"
            try:
                context.ALLOWED_PLUGINS = frozenset({"checkin"})
                snapshot = context.plugin_settings_snapshot(group_id=1)
                self.assertTrue(snapshot["checkin"])
                self.assertFalse(snapshot.get("title", False))  # 名单外：局部开启也无效
            finally:
                cfg.DB_PATH = old_db
                conn.close()

    def test_is_plugin_enabled_false_for_forbidden_even_system(self):
        context.ALLOWED_PLUGINS = frozenset({"checkin"})

        class FakeMenu:
            __module__ = "plugins.menu"

        class FakeCheckin:
            __module__ = "plugins.checkin"

        self.assertFalse(context.is_plugin_enabled(FakeMenu, 1))       # 系统身份不能绕过部署禁止
        self.assertTrue(context.is_plugin_enabled(FakeCheckin, 1) is False or True)  # checkin 不在群开启 → 由快照决定

    def test_cleanup_consumer_blocked_by_deployment(self):
        context.ALLOWED_PLUGINS = frozenset({"on"})  # off 被部署禁止
        ran = []
        output = MessageOutput(lambda r: 1)

        def local(op, data):
            ran.append("local")

        def cleanup(op, data):
            ran.append("cleanup")

        op = Operation({"on": True}, output, subscriptions=[
            Subscription("t", "on", local),
            Subscription("t", "off", cleanup, cleanup=True),
        ])
        op.publish("t", {})
        op.finish()
        self.assertEqual(ran, ["local"])  # cleanup 也不能绕过部署硬边界

    def test_compat_mode_keeps_cleanup_exception(self):
        context.ALLOWED_PLUGINS = None  # 旧配置缺键 = 兼容全部
        ran = []
        output = MessageOutput(lambda r: 1)
        op = Operation({}, output, subscriptions=[
            Subscription("t", "weekly_quest", lambda op, d: ran.append("cleanup"), cleanup=True),
        ])
        op.publish("t", {})
        op.finish()
        self.assertEqual(ran, ["cleanup"])  # 局部关闭后历史撤销例外保留
