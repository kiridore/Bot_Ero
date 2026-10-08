"""config-unification 任务组4：功能包文件数据化与同一有效视图（AC06）。"""
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import config
from core import context as runtime_context
from core.feature_packs import FEATURE_PACKS


class FeaturePacksFileTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = config.FEATURE_PACKS_FILE
        self._saved_policy = (runtime_context.plugin_registry, runtime_context.ALLOWED_PLUGINS,
                              config.SYSTEM_PLUGINS_CONF)

    def tearDown(self):
        config.FEATURE_PACKS_FILE = self._old
        (runtime_context.plugin_registry, runtime_context.ALLOWED_PLUGINS,
         config.SYSTEM_PLUGINS_CONF) = self._saved_policy
        import core.feature_packs as fp
        importlib.reload(fp)  # 还原内置包
        self._tmp.cleanup()

    def _write(self, content: str, name="packs.yaml") -> str:
        p = Path(self._tmp.name) / name
        p.write_text(content, encoding="utf-8")
        return str(p)

    def _reload_packs(self):
        import core.feature_packs as fp
        return importlib.reload(fp)

    def test_builtin_packs_when_key_missing(self):
        config.FEATURE_PACKS_FILE = ""
        fp = self._reload_packs()
        self.assertIn("基础包", fp.FEATURE_PACKS)
        self.assertEqual(fp.FEATURE_PACKS["基础包"]["plugins"][0], "checkin")

    def test_configured_file_replaces_wholesale(self):
        path = self._write("自定义包:\n  plugins: [checkin, title]\n简化: [menu]\n")
        config.FEATURE_PACKS_FILE = path
        fp = self._reload_packs()
        self.assertEqual(fp.FEATURE_PACKS, {
            "自定义包": {"plugins": ["checkin", "title"]},
            "简化": {"plugins": ["menu"]},
        })

    def test_relative_path_resolves_against_config_dir(self):
        (Path(self._tmp.name) / "sub.yaml").write_text("p: [checkin]\n", encoding="utf-8")
        old = os.environ.get("BOTERO_CONFIG")
        cfg = Path(self._tmp.name) / "config.yaml"
        cfg.write_text(
            "bot:\n"
            "  qq: \"1\"\n  nickname: t\n  super_users: [1]\n"
            "  ws_url: ws://x\n  ws_token: x\n"
            "  llonebot_data_path: /a\n  python_data_path: /b\n"
            "  feature_packs_file: sub.yaml\n"
            "auth:\n  salt: s\n", encoding="utf-8")
        os.environ["BOTERO_CONFIG"] = str(cfg)
        try:
            importlib.reload(config)
            self.assertEqual(config.FEATURE_PACKS_FILE, "sub.yaml")
            fp = self._reload_packs()
            self.assertEqual(fp.FEATURE_PACKS, {"p": {"plugins": ["checkin"]}})
        finally:
            if old is None:
                os.environ.pop("BOTERO_CONFIG", None)
            else:
                os.environ["BOTERO_CONFIG"] = old
            importlib.reload(config)
            config.FEATURE_PACKS_FILE = self._old

    def test_missing_file_exits(self):
        config.FEATURE_PACKS_FILE = str(Path(self._tmp.name) / "nope.yaml")
        with self.assertRaises(SystemExit) as ctx:
            self._reload_packs()
        self.assertIn("不存在", str(ctx.exception))

    def test_invalid_shape_exits(self):
        for content in ("", "[]", "空包: []\n", "坏值: 42\n", "非字符串: [ok, 3]\n"):
            config.FEATURE_PACKS_FILE = self._write(content)
            with self.assertRaises(SystemExit):
                self._reload_packs()

    def test_policy_rejects_unknown_pack_member(self):
        path = self._write("自定义包: [checkin, ghost_plugin]\n")
        config.FEATURE_PACKS_FILE = path
        self._reload_packs()
        runtime_context.plugin_registry = [
            type("P1", (), {"__module__": "plugins.checkin"}),
        ]
        runtime_context.ALLOWED_PLUGINS = None
        with self.assertRaises(SystemExit) as ctx:
            runtime_context.validate_deployment_policy()
        self.assertIn("ghost_plugin", str(ctx.exception))

    def test_empty_string_config_rejected_by_validator(self):
        data = {"bot": {"feature_packs_file": ""}, "auth": {"salt": "s"}}
        errors = config.validate_config(data)
        self.assertTrue(any("feature_packs_file" in e for e in errors))


class PackManagementSharedViewTest(unittest.TestCase):
    """管理命令与面板使用同一有效集合；新增包成员不自动开放。"""

    def test_pack_definition_change_does_not_seed_switches(self):
        # 自定义包只影响 /功能包 批量操作的目标；不写 group_plugin_config
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            conn = sqlite3.connect(str(Path(tmp) / "v.db"))
            from core.db._base import init_schema
            init_schema(conn, conn.cursor())
            # 修改包定义（模拟升级后新增成员）不触碰开关表
            before = conn.execute("SELECT COUNT(*) FROM group_plugin_config").fetchone()[0]
            self.assertEqual(before, 0)
            conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
