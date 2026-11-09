"""称号前缀注入钩子（社区版 T0.6）：注册生效 / 未注册降级 / 异常吞没三向断言。"""
import sys
import unittest
from unittest import mock

import core.api as api
import core.context as runtime_context
from core.api import ApiWrapper
from core.cq import at, text


class TestTitlePrefixHook(unittest.TestCase):
    def setUp(self):
        self._old = runtime_context.TITLE_PREFIX_PROVIDER
        self._old_ws = getattr(api, "WS_APP", None)
        api.WS_APP = mock.Mock()  # __init__ 引用模块级 WS_APP，注入不触网
        self.wrapper = ApiWrapper({})

    def tearDown(self):
        runtime_context.TITLE_PREFIX_PROVIDER = self._old
        if self._old_ws is None:
            del api.WS_APP
        else:
            api.WS_APP = self._old_ws

    def test_registered_provider_injects_prefix(self):
        runtime_context.register_title_prefix_provider(lambda db, uid: "「甲·乙」")
        out = self.wrapper._inject_titles_before_at([at(123), text(" hi")])
        self.assertEqual(out[0], text("「甲·乙」 "))
        self.assertEqual(out[1], at(123))

    def test_unregistered_provider_passes_through(self):
        runtime_context.TITLE_PREFIX_PROVIDER = None
        msg = [at(123), text(" hi")]
        out = self.wrapper._inject_titles_before_at(list(msg))
        self.assertEqual(out, tuple(msg))

    def test_provider_exception_swallowed(self):
        def boom(db, uid):
            raise RuntimeError("x")
        runtime_context.register_title_prefix_provider(boom)
        self.assertEqual(self.wrapper._build_title_prefix(123), "")


class TestRealTitlePluginRegistration(unittest.TestCase):
    """独立类：只 import + 断言，不碰全局状态（避免 wipe 真实注册）。"""

    def test_module_import_registers_provider(self):
        import plugins.title  # noqa: F401  模块级注册
        self.assertIsNotNone(runtime_context.TITLE_PREFIX_PROVIDER)


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=2))
