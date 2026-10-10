"""community-registration AC2：私聊准入矩阵与限频提醒。"""
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import config
from core import context as runtime_context
from core.database_manager import DbManager


class RegisterGateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_db = config.DB_PATH
        config.DB_PATH = Path(self._tmp.name) / "gate.db"
        self.db = DbManager()
        self._saved = (runtime_context._register_reminder_at,
                       config.REGISTER_REQUIRE, config.REGISTER_REMINDER_MINUTES)
        runtime_context._register_reminder_at.clear()
        config.REGISTER_REQUIRE = True
        config.REGISTER_REMINDER_MINUTES = 30
        self._old_super = config.SUPER_USER

    def tearDown(self):
        runtime_context._register_reminder_at.clear()
        (runtime_context._register_reminder_at,) = (self._saved[0],)
        config.REGISTER_REQUIRE, config.REGISTER_REMINDER_MINUTES = self._saved[1], self._saved[2]
        config.SUPER_USER = self._old_super
        self.db.conn.close()
        config.DB_PATH = self._old_db
        self._tmp.cleanup()

    def _ctx(self, text_body, uid=777):
        return {"post_type": "message", "message_type": "private", "user_id": uid,
                "message": [{"type": "text", "data": {"text": text_body}}]}

    def test_require_off_means_no_gate(self):
        config.REGISTER_REQUIRE = False
        self.assertIsNone(runtime_context.register_gate("message", None, 777))
        self.assertFalse(runtime_context.should_remind_register(777, self._ctx("/打卡")))

    def test_unregistered_private_restricted(self):
        gate = runtime_context.register_gate("message", None, 777)
        self.assertEqual(gate, runtime_context.REGISTRATION_ALLOWLIST)
        self.assertIn("register", gate)
        self.assertIn("show_menu", gate)
        self.assertNotIn("checkin", gate)

    def test_group_notice_meta_and_registered_unrestricted(self):
        self.assertIsNone(runtime_context.register_gate("message", 10, 777))
        self.assertIsNone(runtime_context.register_gate("notice", None, 777))
        self.assertIsNone(runtime_context.register_gate("meta", None, 777))
        self.db.community.agree_eula(777, "v1")
        self.assertIsNone(runtime_context.register_gate("message", None, 777))

    def test_super_user_bypasses_gate(self):
        config.SUPER_USER = [777]
        self.assertIsNone(runtime_context.register_gate("message", None, 777))
        self.assertFalse(runtime_context.should_remind_register(777, self._ctx("/打卡")))

    def test_reminder_only_for_blocked_commands_and_rate_limited(self):
        # 非命令消息不提醒
        self.assertFalse(runtime_context.should_remind_register(777, self._ctx("你好")))
        # 放行命令不提醒
        for cmd in ("/注册", "/同意EULA", "/同意eula", "/菜单", "/菜單"):
            runtime_context._register_reminder_at.clear()
            self.assertFalse(runtime_context.should_remind_register(777, self._ctx(cmd)), cmd)
        # 其他命令提醒一次，窗口内不重复
        runtime_context._register_reminder_at.clear()
        self.assertTrue(runtime_context.should_remind_register(777, self._ctx("/打卡")))
        self.assertFalse(runtime_context.should_remind_register(777, self._ctx("/抽奖")))
        self.assertFalse(runtime_context.should_remind_register(777, self._ctx("/打卡")))
        # 窗口过后恢复（缩短窗口模拟）
        config.REGISTER_REMINDER_MINUTES = 0
        self.assertTrue(runtime_context.should_remind_register(777, self._ctx("/打卡")))

    def test_gate_failure_is_fail_closed(self):
        # 注册状态读取失败时不得放行（防绕过）：fail-closed 回落为限制集
        self.db.conn.execute("DROP TABLE user_accounts")
        self.db.conn.commit()
        self.assertEqual(runtime_context.register_gate("message", None, 778),
                         runtime_context.REGISTRATION_ALLOWLIST)


if __name__ == "__main__":
    unittest.main(verbosity=2)
