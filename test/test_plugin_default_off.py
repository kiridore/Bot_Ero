"""插件启停白名单语义：注册而未配置的插件默认全关（无任何自动播种，含全新部署）。

运行: python -m pytest test/test_plugin_default_off.py
"""

from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import config
import core.context as ctx


class DefaultOffTest(unittest.TestCase):
    def setUp(self):
        class Fake:
            description = "默认关测试"
            __module__ = "plugins.fake_default_off"

        self.fake = Fake
        ctx.plugin_registry.append(Fake)
        self.addCleanup(ctx.plugin_registry.remove, Fake)
        conn = sqlite3.connect(str(config.DB_PATH))
        conn.execute(
            "DELETE FROM group_plugin_config WHERE plugin_name = 'fake_default_off'"
        )
        conn.commit()
        conn.close()

    def test_unconfigured_plugin_disabled_everywhere(self):
        for gid in (0, config.DEFAULT_GROUP_ID, 4321):
            self.assertFalse(
                ctx.is_plugin_enabled(self.fake, gid), f"gid={gid} 应默认禁用"
            )
        self.assertFalse(
            ctx.is_plugin_enabled(self.fake, None), "私聊（None→0）应默认禁用"
        )

    def test_enable_via_row_only_for_that_group(self):
        conn = sqlite3.connect(str(config.DB_PATH))
        conn.execute(
            "INSERT OR IGNORE INTO group_plugin_config (group_id, plugin_name) VALUES (?, ?)",
            (config.DEFAULT_GROUP_ID, "fake_default_off"),
        )
        conn.commit()
        conn.close()
        self.assertTrue(ctx.is_plugin_enabled(self.fake, config.DEFAULT_GROUP_ID))
        self.assertFalse(
            ctx.is_plugin_enabled(self.fake, 4321), "其他群仍默认禁用"
        )
        self.assertFalse(
            ctx.is_plugin_enabled(self.fake, None), "私聊桶仍默认禁用"
        )


if __name__ == "__main__":
    unittest.main()
