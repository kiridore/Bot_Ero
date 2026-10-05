"""系统插件集配置化（社区版 T0.4）：缺省集回落 + bot.system_plugins 精确替换 + 移出项回归按群开关。"""
import importlib
import sys
import unittest
from unittest import mock

import core.config as config
import core.context as context

_DEFAULT = frozenset({
    "menu", "group_manager", "startup_changelog", "backup",
    "update", "auto_friend", "welcome", "message_logger",
})


class TestDefaultSystemPlugins(unittest.TestCase):
    """conftest 临时配置无 system_plugins 键 → 内置缺省集，私有行为零变化（验收 1）。"""

    def test_default_set_when_unconfigured(self):
        self.assertEqual(context.SYSTEM_PLUGINS, _DEFAULT)
        self.assertEqual(context._DEFAULT_SYSTEM_PLUGINS, _DEFAULT)


class TestConfiguredSystemPlugins(unittest.TestCase):
    """bot.system_plugins 非空 → 精确替换（验收 2、3）。"""

    def test_custom_set_replaces_default(self):
        _saved_provider = context.TITLE_PREFIX_PROVIDER
        _saved_registry = list(context.plugin_registry)
        try:
            with mock.patch.object(config, "SYSTEM_PLUGINS_CONF", ["menu", "register"]):
                importlib.reload(context)
                self.assertEqual(context.SYSTEM_PLUGINS, frozenset({"menu", "register"}))
                # 验收 3：menu 仍系统级免检；message_logger 被移出，无 DB 行 → False
                class _P:
                    __module__ = "plugins.menu"
                self.assertTrue(context.is_plugin_enabled(_P, 12345))
                class _M:
                    __module__ = "plugins.message_logger"
                self.assertFalse(context.is_plugin_enabled(_M, 12345))
        finally:
            importlib.reload(context)  # 还原真实配置
            # reload 会抹掉运行期注册态（模块级全局重置为初值），保存还原：
            # ponytail: 手工列举，context 新增运行期全局时需同步补入
            context.TITLE_PREFIX_PROVIDER = _saved_provider
            context.plugin_registry[:] = _saved_registry
        self.assertEqual(context.SYSTEM_PLUGINS, _DEFAULT)

    def test_plugin_key_unchanged(self):
        class _P:
            __module__ = "plugins.menu"
        self.assertEqual(context.plugin_key(_P), "menu")


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=2))
