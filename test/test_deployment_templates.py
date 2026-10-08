"""config-unification 任务组5：公开候选配置模板验收（AC09）。

纯函数校验：不 importlib.reload、不换 BOTERO_CONFIG、不写任何数据库；
模块级常量推导用独立子进程拿隔离配置验证（_env.write_config 同款隔离）。
"""
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TEMPLATE = PROJECT_ROOT / "config.public.example.yaml"
PACKS = PROJECT_ROOT / "feature_packs_public.yaml"

SYSTEM = {"menu", "group_manager", "backup", "update", "auto_friend"}
BASICS = {"checkin", "checkin_recall", "roll_back", "remedy_checkin",
          "week_checkin_display", "all_checkin_display", "week_list",
          "personal_records", "leaderboard"}
ALLOWED = SYSTEM | BASICS | {"monitor"}
PRIVATE_OR_ECONOMY = {"ff_news", "weekly_report", "startup_changelog", "immortal_lottery",
                      "who_is_spy", "lottery", "title", "weekly_quest", "redeem_shop",
                      "redeem_code", "grant_points_all", "message_logger", "dice"}


class TemplateContentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import plugins  # noqa: F401  触发自动注册（conftest 已提供隔离配置）
        import core.context as context
        cls.registered = {context.plugin_key(p) for p in context.plugin_registry}
        cls.data = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))

    def test_template_passes_shared_validation(self):
        from core.config import validate_config
        self.assertEqual(validate_config(self.data), [])

    def test_allowed_boundary_exact_and_registered(self):
        allowed = set(self.data["bot"]["allowed_plugins"])
        self.assertEqual(allowed, ALLOWED)
        self.assertTrue(allowed <= self.registered, f"未注册：{allowed - self.registered}")
        self.assertFalse(allowed & PRIVATE_OR_ECONOMY,
                         f"公开名单混入私域/经济插件：{allowed & PRIVATE_OR_ECONOMY}")

    def test_system_subset_of_allowed_and_registered(self):
        system = set(self.data["bot"]["system_plugins"])
        self.assertEqual(system, SYSTEM)
        self.assertTrue(system <= set(self.data["bot"]["allowed_plugins"]))
        self.assertTrue(system <= self.registered)

    def test_feature_pack_file_members_valid(self):
        from core.feature_packs import _load_configured
        packs = _load_configured(str(PACKS))
        self.assertEqual(set(packs), {"打卡基础"})
        members = set(packs["打卡基础"]["plugins"])
        self.assertEqual(members, BASICS)
        self.assertTrue(members <= ALLOWED)
        self.assertTrue(members <= self.registered)

    def test_edition_label_is_descriptive_only(self):
        from core.config import validate_config
        results = []
        for label in ("community", "private", None):
            data = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
            if label is None:
                data["bot"].pop("edition", None)
            else:
                data["bot"]["edition"] = label
            results.append(validate_config(data))
        self.assertEqual(results, [[], [], []])  # 标签不影响校验结果

    def test_paired_optional_services_absent(self):
        self.assertNotIn("onebot", self.data)   # 不配置 = 不启用 HTTP，不因标签要求
        self.assertNotIn("timeline", self.data)

    def test_menu_after_enabling_basics_matches_first_release(self):
        from plugins.menu.entries import render_menu
        enabled = {key: True for key in SYSTEM | BASICS}
        menu = render_menu(enabled, is_super=False, in_group=True)
        for expected in ("/打卡", "/补卡", "/单日补卡", "/撤回打卡", "/本周打卡图",
                         "/ALL", "/本周板油", "/档案", "/排名"):
            self.assertIn(expected, menu)
        for absent in ("/抽奖", "/一键抽奖", "/周常", "/商店", "/称号", "/仙人彩",
                       "/占卜", "/创建游戏", "/活动", "/跑团", "/FF新闻"):
            self.assertNotIn(absent, menu, f"首版菜单不应出现 {absent}")
        self.assertNotIn("【管理员指令】", menu)
        self.assertIn("【管理员指令】", render_menu(enabled, is_super=True, in_group=True))


class TemplateIsolatedLoadTest(unittest.TestCase):
    """子进程内用真实加载路径验证模板派生常量与默认关闭语义。"""

    def _run_child(self, workdir: Path) -> str:
        (workdir / "feature_packs_public.yaml").write_text(
            PACKS.read_text(encoding="utf-8"), encoding="utf-8")
        (workdir / "community.yaml").write_text(
            (PROJECT_ROOT / "text_packs/community.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (workdir / "config.yaml").write_text(
            TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
        script = (
            "import os, json\n"
            "os.environ['BOTERO_CONFIG'] = r'%s'\n"
            "from core import config\n"
            "import core.context as context\n"
            "import plugins  # 自动注册\n"
            "context.validate_deployment_policy()\n"
            "snap_group = context.plugin_settings_snapshot(group_id=999999)\n"
            "snap_private = context.plugin_settings_snapshot(user_id=888888)\n"
            "print(json.dumps({\n"
            "  'allowed': sorted(context.ALLOWED_PLUGINS),\n"
            "  'system': sorted(context.SYSTEM_PLUGINS),\n"
            "  'packs': {k: v['plugins'] for k, v in __import__('core.feature_packs', fromlist=['FEATURE_PACKS']).FEATURE_PACKS.items()},\n"
            "  'new_group_checkin': snap_group.get('checkin', False),\n"
            "  'new_private_leaderboard': snap_private.get('leaderboard', False),\n"
            "  'menu_plugin_on': snap_group.get('menu', False),\n"
            "  'cooldown': config.COMMUNITY_CMD_COOLDOWN_SECONDS,\n"
            "}))\n" % (workdir / "config.yaml")
        )
        result = subprocess.run([sys.executable, "-c", script], capture_output=True,
                                text=True, encoding="utf-8", cwd=PROJECT_ROOT, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip().splitlines()[-1]

    def test_template_loads_in_isolation_with_default_closed_semantics(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            out = json.loads(self._run_child(Path(tmp)))
        self.assertEqual(set(out["allowed"]), ALLOWED)
        self.assertEqual(set(out["system"]), SYSTEM)
        self.assertEqual(set(out["packs"]["打卡基础"]), BASICS)
        self.assertFalse(out["new_group_checkin"])      # 新群默认关闭
        self.assertFalse(out["new_private_leaderboard"])  # 新账号默认关闭
        self.assertTrue(out["menu_plugin_on"])          # 系统插件恒开
        self.assertEqual(out["cooldown"], 3)            # 模板显式配置


if __name__ == "__main__":
    unittest.main(verbosity=2)
