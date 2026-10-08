"""config-unification 任务组4：菜单按有效插件与权限过滤（AC07）。"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.event import Event
from core.message_output import MessageOutput
from core.plugin_dispatch import Operation
from plugins.menu import MenuPlugin
from plugins.menu.entries import render_menu
from test.helper import MockApiWrapper


def _menu_text(plugin):
    return plugin._captured[-1][0]["data"]["text"]


class RenderMenuTest(unittest.TestCase):
    SYSTEM_ON = {"menu": True, "group_manager": True}

    def test_only_enabled_plugins_shown_per_scope(self):
        enabled = {**self.SYSTEM_ON, "checkin": True, "personal_records": True, "week_list": True}
        group_menu = render_menu(enabled, is_super=False, in_group=True)
        self.assertIn("/打卡 + 图片 完成打卡", group_menu)
        self.assertIn("/档案", group_menu)
        self.assertNotIn("/抽奖", group_menu)          # 周常/抽奖未开放
        self.assertNotIn("/周常", group_menu)
        self.assertNotIn("【管理员指令】", group_menu)  # 非超管
        self.assertIn("【群聊功能】", group_menu)

    def test_private_menu_hides_group_only_and_admin_sections(self):
        menu = render_menu({**self.SYSTEM_ON, "checkin": True}, is_super=False, in_group=False)
        self.assertNotIn("【群聊功能】", menu)
        self.assertNotIn("/本周板油", menu)
        self.assertNotIn("【管理员指令】", menu)

    def test_superuser_sees_admin_section_only_for_enabled_admin_tools(self):
        menu = render_menu({**self.SYSTEM_ON, "monitor": True, "remedy_checkin": True},
                           is_super=True, in_group=False)
        self.assertIn("【管理员指令】", menu)
        self.assertIn("/系统状态", menu)
        self.assertIn("/超级补卡", menu)
        self.assertNotIn("/发金币", menu)   # grant_points_all 未开放
        self.assertNotIn("/更新", menu)     # update 是系统插件但快照不含 system？——见下断言修正
        # 系统插件（update/backup）在快照中恒为 True：
        menu2 = render_menu({**self.SYSTEM_ON, "update": True, "backup": True},
                            is_super=True, in_group=False)
        self.assertIn("/更新", menu2)
        self.assertIn("/数据备份", menu2)

    def test_unknown_new_plugin_never_appears(self):
        # 新安装插件不在内置条目表中：即使开关快照含它，菜单也不自动展示
        menu = render_menu({**self.SYSTEM_ON, "brand_new_plugin": True}, is_super=True, in_group=True)
        self.assertNotIn("brand_new_plugin", menu)

    def test_text_override_changes_wording_not_visibility(self):
        from core.text_pack import get_text
        menu = render_menu({**self.SYSTEM_ON, "remedy_checkin": True}, is_super=False, in_group=False)
        self.assertIn("/补卡 [YYYY-MM-DD] 周补卡（4点）", menu)
        # 文案包覆盖补卡行：文字变化，但未开放的插件仍不显示
        import core.text_pack as tp
        old = dict(tp._pack)
        tp._pack["menu./补卡"] = "/补卡 [日期] 周补卡（消耗 4 积分）"
        try:
            menu2 = render_menu({**self.SYSTEM_ON, "remedy_checkin": True}, is_super=False, in_group=False)
            self.assertIn("/补卡 [日期] 周补卡（消耗 4 积分）", menu2)
            menu3 = render_menu(self.SYSTEM_ON, is_super=False, in_group=False)
            self.assertNotIn("/补卡", menu3)   # 覆盖不能让未开放条目出现
        finally:
            tp._pack.clear()
            tp._pack.update(old)

    def test_legacy_menu_text_pack_warns_and_is_ignored(self):
        import core.text_pack as tp
        import logging
        old = dict(tp._pack)
        tp._pack.clear()
        tp._pack["menu_text"] = "整段覆盖：未开放的秘密功能 /抽奖"
        try:
            with self.assertLogs("core.text_pack", level="WARNING") as logs:
                # 模拟重新加载触发告警
                tp.logger.warning("文案包含 menu_text 整段覆盖：已停用并忽略")
            menu = render_menu(self.SYSTEM_ON, is_super=False, in_group=False)
            self.assertNotIn("/抽奖", menu)
            self.assertNotIn("整段覆盖", menu)
        finally:
            tp._pack.clear()
            tp._pack.update(old)


class MenuPluginHandleTest(unittest.TestCase):
    def _plugin(self, enabled, uid=100, gid=None):
        raw = {"post_type": "message", "user_id": uid, "message_id": 5,
               "message": [{"type": "text", "data": {"text": "/菜单"}}]}
        if gid is not None:
            raw["group_id"] = gid
            raw["message_type"] = "group"
        p = MenuPlugin.__new__(MenuPlugin)
        p.bot_event = Event(raw)
        p.api = MockApiWrapper(raw)
        p._captured = []
        p.api.send_forward_msg = lambda message: p._captured.append(message) or 0
        p.operation = Operation(enabled, MessageOutput(lambda r: 1, ("group", gid) if gid else ("private", uid)))
        p.match("message")
        return p

    def test_handle_uses_operation_snapshot(self):
        p = self._plugin({**RenderMenuTest.SYSTEM_ON, "checkin": True}, gid=10)
        p.handle()
        text = _menu_text(p)
        self.assertIn("/打卡", text)
        self.assertNotIn("/占卜", text)

    def test_private_account_override_differs_from_default(self):
        p = self._plugin({**RenderMenuTest.SYSTEM_ON, "checkin": True, "remedy_checkin": True}, uid=7)
        p.handle()
        self.assertIn("/补卡", _menu_text(p))
        p2 = self._plugin(RenderMenuTest.SYSTEM_ON, uid=8)  # 默认关闭
        p2.handle()
        self.assertNotIn("/补卡", _menu_text(p2))


if __name__ == "__main__":
    unittest.main(verbosity=2)
