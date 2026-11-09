"""config-unification 任务组1：统一校验、版名无关与部署引用验证。

只使用纯函数与隔离配置文件；不 import main、不触碰生产数据。
"""
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from core import config


def _base_data() -> dict:
    """最小可加载配置：无 default_group / onebot / timeline / allowed_plugins。"""
    return {
        "bot": {
            "qq": "123456", "nickname": "t", "super_users": [1],
            "ws_url": "ws://127.0.0.1:3001", "ws_token": "x",
            "llonebot_data_path": "/tmp/a", "python_data_path": "./server_data",
        },
        "auth": {"salt": "s"},
    }


class TestValidateConfig(unittest.TestCase):
    def test_minimal_bot_only_passes(self):
        self.assertEqual(config.validate_config(_base_data()), [])

    def test_register_section_shape(self):
        ok = _base_data()
        ok["register"] = {"require": True, "eula_file": "docs/eula/v1.md",
                          "default_pack": "打卡基础", "reminder_minutes": 30}
        self.assertEqual(config.validate_config(ok), [])
        cases = [
            ({"require": "yes"}, "require 必须是布尔值"),
            ({"reminder_minutes": -1}, "reminder_minutes"),
            ({"reminder_minutes": "30"}, "reminder_minutes"),
            ({"eula_file": ""}, "eula_file"),
            ({"default_pack": 7}, "default_pack"),
        ]
        for section, expected in cases:
            data = _base_data()
            data["register"] = section
            errors = config.validate_config(data)
            self.assertTrue(any(expected in e for e in errors), (section, errors))
        # 缺省 register 节 = 不启用，零错误
        self.assertEqual(config.validate_config(_base_data()), [])

    def test_required_registration_validates_eula_and_pack(self):
        import core.context as context
        saved = (config.REGISTER_REQUIRE, config.REGISTER_EULA_FILE,
                 config.REGISTER_DEFAULT_PACK, context.plugin_registry,
                 context.ALLOWED_PLUGINS, config.SYSTEM_PLUGINS_CONF)
        try:
            context.plugin_registry = [type("R1", (), {"__module__": "plugins.checkin"})]
            context.ALLOWED_PLUGINS = None
            config.SYSTEM_PLUGINS_CONF = []
            config.REGISTER_REQUIRE = True
            config.REGISTER_DEFAULT_PACK = "基础包"
            config.REGISTER_EULA_FILE = "docs/eula/v1.md"
            context.validate_deployment_policy()  # 文件存在、包存在 → 通过
            config.REGISTER_EULA_FILE = "docs/eula/missing.md"
            with self.assertRaises(SystemExit) as ctx1:
                context.validate_deployment_policy()
            self.assertIn("register.eula_file", str(ctx1.exception))
            config.REGISTER_EULA_FILE = "docs/eula/v1.md"
            config.REGISTER_DEFAULT_PACK = "不存在的包"
            with self.assertRaises(SystemExit) as ctx2:
                context.validate_deployment_policy()
            self.assertIn("default_pack", str(ctx2.exception))
        finally:
            (config.REGISTER_REQUIRE, config.REGISTER_EULA_FILE,
             config.REGISTER_DEFAULT_PACK, context.plugin_registry,
             context.ALLOWED_PLUGINS, config.SYSTEM_PLUGINS_CONF) = saved

    def test_missing_required_reports_all(self):
        data = _base_data()
        del data["bot"]["qq"]
        data["auth"]["salt"] = ""
        errors = config.validate_config(data)
        self.assertTrue(any("bot.qq" in e for e in errors))
        self.assertTrue(any("auth.salt" in e for e in errors))

    def test_paired_service_keys(self):
        data = _base_data()
        data["timeline"] = {"url": "http://t"}
        self.assertTrue(any("timeline" in e for e in config.validate_config(data)))
        data["timeline"]["token"] = "tk"
        data["onebot"] = {"http_url": "http://o"}
        self.assertTrue(any("onebot" in e for e in config.validate_config(data)))
        data["onebot"]["token"] = "ok"
        self.assertEqual(config.validate_config(data), [])
        data["timeline"] = {"token": "tk"}  # 只有 token 没有 url 同样不成对
        self.assertTrue(any("timeline" in e for e in config.validate_config(data)))

    def test_allowed_plugins_shape(self):
        data = _base_data()
        data["bot"]["allowed_plugins"] = ["checkin", "title"]
        self.assertEqual(config.validate_config(data), [])
        data["bot"]["allowed_plugins"] = "checkin"          # 非列表
        self.assertTrue(any("allowed_plugins" in e for e in config.validate_config(data)))
        data["bot"]["allowed_plugins"] = ["checkin", 42]   # 非字符串成员
        self.assertTrue(any("allowed_plugins" in e for e in config.validate_config(data)))
        data["bot"]["allowed_plugins"] = []                # 显式空列表不得解释为全部
        errors = config.validate_config(data)
        self.assertTrue(any("allowed_plugins" in e for e in errors))
        self.assertTrue(any("空列表" in e for e in errors))

    def test_system_plugins_shape(self):
        data = _base_data()
        data["bot"]["system_plugins"] = []                 # 显式空列表：要内置集合请删键
        errors = config.validate_config(data)
        self.assertTrue(any("system_plugins" in e for e in errors))
        data["bot"]["system_plugins"] = "menu"
        self.assertTrue(any("system_plugins" in e for e in config.validate_config(data)))

    def test_load_exits_with_all_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = _base_data()
            data["timeline"] = {"url": "http://t"}
            data["bot"]["allowed_plugins"] = []
            p = Path(tmp) / "config.yaml"
            p.write_text(yaml.safe_dump(data), encoding="utf-8")
            with self.assertRaises(SystemExit) as ctx:
                config._load(p)
            message = str(ctx.exception)
            self.assertIn("timeline", message)
            self.assertIn("allowed_plugins", message)


class TestEditionIrrelevance(unittest.TestCase):
    """同一有效配置仅改版名标签：校验结果与运行常量完全一致（AC03/AC06）。"""

    def _reload_with(self, cfg_path: str):
        import os
        old = os.environ.get("BOTERO_CONFIG")
        os.environ["BOTERO_CONFIG"] = cfg_path
        try:
            importlib.reload(config)
        finally:
            if old is None:
                os.environ.pop("BOTERO_CONFIG", None)
            else:
                os.environ["BOTERO_CONFIG"] = old

    def test_label_does_not_change_validation_or_defaults(self):
        raw = _base_data()
        raw["bot"]["default_group"] = 42
        results = []
        snapshots = []
        with tempfile.TemporaryDirectory() as tmp:
            for index, label in enumerate(("private", "community", "saas", None)):
                data = yaml.safe_load(yaml.safe_dump(raw))
                if label is None:
                    data["bot"].pop("edition", None)
                else:
                    data["bot"]["edition"] = label
                p = Path(tmp) / f"config{index}.yaml"
                p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
                results.append(config.validate_config(yaml.safe_load(p.read_text(encoding="utf-8"))))
                self._reload_with(str(p))
                snapshots.append((
                    config.COMMUNITY_CMD_COOLDOWN_SECONDS, config.DEFAULT_GROUP_ID,
                    tuple(config.ALLOWED_PLUGINS_CONF or ()),
                    tuple(config.SYSTEM_PLUGINS_CONF),
                    config.TIMELINE_URL, config.ONEBOT_HTTP_URL,
                ))
            self._reload_with(str(Path(os.environ.get("BOTERO_CONFIG", "config.yaml"))))
        self.assertEqual(results, [[], [], [], []])
        self.assertEqual(len(set(snapshots)), 1, f"版名标签不应改变常量：{snapshots}")
        self.assertEqual(snapshots[0][0], 0)  # 冷却统一缺省 0

    def test_cooldown_explicit_value_independent_of_label(self):
        raw = _base_data()
        raw["community"] = {"cmd_cooldown_seconds": 7}
        with tempfile.TemporaryDirectory() as tmp:
            for index, label in enumerate(("private", "community")):
                data = yaml.safe_load(yaml.safe_dump(raw))
                data["bot"]["edition"] = label
                p = Path(tmp) / f"c{index}.yaml"
                p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
                self._reload_with(str(p))
                self.assertEqual(config.COMMUNITY_CMD_COOLDOWN_SECONDS, 7)
            self._reload_with(os.environ.get("BOTERO_CONFIG", "config.yaml"))


class TestPanelSharedValidation(unittest.TestCase):
    """面板存盘与启动共用同一校验（AC05）：精简配置可保存，成对/名单错误被拒。"""

    def test_panel_uses_shared_validator(self):
        from core.web_panel import _validate_config
        minimal = yaml.safe_dump(_base_data(), allow_unicode=True)
        self.assertIsNone(_validate_config(minimal))
        broken = yaml.safe_dump({**_base_data(), "timeline": {"url": "http://t"}}, allow_unicode=True)
        err = _validate_config(broken)
        self.assertIsNotNone(err)
        self.assertIn("timeline", err)
        empty_allowed = yaml.safe_dump({**_base_data(), "bot": {**_base_data()["bot"], "allowed_plugins": []}},
                                       allow_unicode=True)
        self.assertIsNotNone(_validate_config(empty_allowed))


class TestDeploymentPolicyValidation(unittest.TestCase):
    """validate_deployment_policy：注册完成后校验引用与冲突（AC01）。"""

    def setUp(self):
        import core.context as context
        self.context = context
        # ponytail: 不用 importlib.reload 还原——reload 会抹掉 TITLE_PREFIX_PROVIDER 等运行期注册态（记忆 #130）
        self._saved = (context.plugin_registry, context.ALLOWED_PLUGINS,
                       context.SYSTEM_PLUGINS, config.SYSTEM_PLUGINS_CONF)

    def tearDown(self):
        (self.context.plugin_registry, self.context.ALLOWED_PLUGINS,
         self.context.SYSTEM_PLUGINS, config.SYSTEM_PLUGINS_CONF) = self._saved

    def _with_registry(self, *names):
        self.context.plugin_registry = [
            type(f"P{index}", (), {"__module__": f"plugins.{name}"})
            for index, name in enumerate(names)
        ]

    def test_empty_registry_is_a_timing_error(self):
        self.context.plugin_registry = []
        self.context.ALLOWED_PLUGINS = None
        with self.assertRaises(SystemExit) as ctx:
            self.context.validate_deployment_policy()
        self.assertIn("注册表为空", str(ctx.exception))

    def test_unknown_allowed_plugin_exits(self):
        self._with_registry("checkin", "title")
        self.context.ALLOWED_PLUGINS = frozenset({"checkin", "no_such"})
        with self.assertRaises(SystemExit) as ctx:
            self.context.validate_deployment_policy()
        self.assertIn("no_such", str(ctx.exception))

    def test_system_not_subset_of_allowed_exits(self):
        self._with_registry("menu", "checkin")
        config.SYSTEM_PLUGINS_CONF = []
        self.context.SYSTEM_PLUGINS = frozenset({"menu"})
        self.context.ALLOWED_PLUGINS = frozenset({"checkin"})  # 缺 menu
        with self.assertRaises(SystemExit) as ctx:
            self.context.validate_deployment_policy()
        self.assertIn("menu", str(ctx.exception))

    def test_unknown_system_plugin_exits(self):
        self._with_registry("menu")
        config.SYSTEM_PLUGINS_CONF = ["menu", "ghost"]
        self.context.SYSTEM_PLUGINS = frozenset({"menu", "ghost"})
        self.context.ALLOWED_PLUGINS = None
        with self.assertRaises(SystemExit) as ctx:
            self.context.validate_deployment_policy()
        self.assertIn("ghost", str(ctx.exception))

    def test_valid_explicit_policy_passes(self):
        self._with_registry("menu", "checkin", "title", "group_manager")
        config.SYSTEM_PLUGINS_CONF = ["menu", "group_manager"]
        self.context.SYSTEM_PLUGINS = frozenset({"menu", "group_manager"})
        self.context.ALLOWED_PLUGINS = frozenset({"menu", "group_manager", "checkin", "title"})
        self.context.validate_deployment_policy()  # 不退出即通过

    def test_compat_mode_passes_without_allowed(self):
        self._with_registry("menu", "checkin")
        config.SYSTEM_PLUGINS_CONF = []
        self.context.SYSTEM_PLUGINS = self.context._DEFAULT_SYSTEM_PLUGINS
        self.context.ALLOWED_PLUGINS = None  # 旧配置：缺键 = 全部允许
        self.context.validate_deployment_policy()


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=2))
