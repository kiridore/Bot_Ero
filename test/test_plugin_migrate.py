"""group_plugin_config 迁移播种语义：仅建表时播种，已有表禁用状态不得复活。

运行: python -m pytest test/test_plugin_migrate.py
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


class MigrateSeedTest(unittest.TestCase):
    def setUp(self):
        # conftest 已把 config.DB_PATH 重定向到会话临时库；每个用例重建表状态
        self.db = str(config.DB_PATH)
        conn = sqlite3.connect(self.db)
        conn.execute("DROP TABLE IF EXISTS group_plugin_config")
        conn.commit()
        conn.close()

    def _rows(self, gid):
        conn = sqlite3.connect(self.db)
        rows = conn.execute(
            "SELECT plugin_name FROM group_plugin_config WHERE group_id = ?", (gid,)
        ).fetchall()
        conn.close()
        return {r[0] for r in rows}

    def test_seed_only_when_table_created(self):
        # 注册表为空时（测试进程未注册插件），播种行数为 0 但表应被创建
        ctx.migrate_group_plugin_config()
        conn = sqlite3.connect(self.db)
        has = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'group_plugin_config'"
        ).fetchone() is not None
        conn.close()
        self.assertTrue(has, "表应被创建")

    def test_existing_table_not_reseeded(self):
        ctx.migrate_group_plugin_config()  # 建表（空 registry，播种 0 行）
        gid = config.DEFAULT_GROUP_ID

        # 注入假插件类（测试进程 plugin_registry 为空，必须注入才能让重播可见）
        class FakePlugin:
            __module__ = "plugins.fake_plugin"

        ctx.plugin_registry.append(FakePlugin)
        self.addCleanup(ctx.plugin_registry.remove, FakePlugin)

        ctx.migrate_group_plugin_config()  # 表已存在 → 不得重新播种
        self.assertNotIn(
            "fake_plugin", self._rows(gid),
            "表已存在时不得重新播种（禁用状态不得因重启复活）")


if __name__ == "__main__":
    unittest.main()
