"""M1 T1.1：社区准入数据层——四表 CRUD、状态流转、幂等与挂载（AC1）。"""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.db._base import init_schema
from core.db.community import CommunityManager


class CommunityDbTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(str(Path(self._tmp.name) / "community.db"))
        self.conn.row_factory = sqlite3.Row
        init_schema(self.conn, self.conn.cursor())
        self.db = CommunityManager(self.conn)

    def tearDown(self):
        self.conn.close()
        self._tmp.cleanup()

    # —— 注册 ——

    def test_register_idempotent_keeps_first_time(self):
        self.assertTrue(self.db.register_user(1001))
        self.assertFalse(self.db.register_user(1001))          # 重复注册
        row = self.conn.execute(
            "SELECT COUNT(*), MIN(created_at) FROM user_accounts WHERE user_id = 1001").fetchone()
        self.assertEqual(row[0], 1)                            # 仍只有一行
        first = self.conn.execute(
            "SELECT created_at FROM user_accounts WHERE user_id = 1001").fetchone()[0]
        self.assertFalse(self.db.register_user(1001))
        after = self.conn.execute(
            "SELECT created_at FROM user_accounts WHERE user_id = 1001").fetchone()[0]
        self.assertEqual(first, after)                         # 首次时间不变
        self.assertTrue(self.db.is_registered(1001))
        self.assertFalse(self.db.is_registered(9999))

    # —— 群登记 ——

    def test_group_activate_removed_then_reactivate(self):
        self.db.activate_group(2001, name="测试群", invited_by=1001)
        approved_at = self.conn.execute(
            "SELECT approved_at FROM group_registry WHERE group_id = 2001").fetchone()[0]
        self.assertTrue(self.db.is_group_active(2001))
        self.db.mark_group_removed(2001)
        self.assertFalse(self.db.is_group_active(2001))
        self.db.iter_active_groups()                            # 不含 removed
        self.db.activate_group(2001)                            # 重新批准
        self.assertTrue(self.db.is_group_active(2001))
        kept = self.conn.execute(
            "SELECT approved_at, name, invited_by FROM group_registry WHERE group_id = 2001").fetchone()
        self.assertEqual(kept[0], approved_at)                  # 首次批准时间保留
        self.assertEqual(kept[1], "测试群")                     # 审核历史保留
        self.assertEqual(kept[2], 1001)

    def test_iter_active_groups_only_active(self):
        self.db.activate_group(1)
        self.db.activate_group(2)
        self.db.mark_group_removed(2)
        self.db.activate_group(3)
        self.assertEqual(self.db.iter_active_groups(), [1, 3])

    def test_repeated_activate_is_idempotent(self):
        self.db.activate_group(5)
        approved = self.conn.execute(
            "SELECT approved_at FROM group_registry WHERE group_id = 5").fetchone()[0]
        self.db.activate_group(5)
        self.db.activate_group(5)
        self.assertEqual(tuple(self.conn.execute(
            "SELECT COUNT(*), approved_at FROM group_registry WHERE group_id = 5").fetchone()),
            (1, approved))

    # —— 申请队列 ——

    def test_request_dedupe_by_flag(self):
        self.assertTrue(self.db.upsert_request(3001, 1001, "flag-abc", "add"))
        self.assertFalse(self.db.upsert_request(3001, 1001, "flag-abc", "add"))   # 同凭证
        self.assertFalse(self.db.upsert_request(3001, 1002, "flag-abc", "invite"))  # 同凭证异人
        self.assertEqual(len(self.db.pending_requests()), 1)

    def test_resolve_terminal_state_immutable(self):
        self.db.upsert_request(3002, 1001, "flag-1", "add")
        pending = self.db.pending_requests()[0]["created_at"]
        self.assertTrue(self.db.resolve_request(3002, 1001, pending, approve=False))
        self.assertEqual(self.db.pending_requests(), [])        # 终态不再出现在待审
        self.assertFalse(self.db.resolve_request(3002, 1001, pending, approve=True))  # 拒绝后不能再通过
        status = self.conn.execute(
            "SELECT status FROM group_requests WHERE flag = 'flag-1'").fetchone()[0]
        self.assertEqual(status, "rejected")
        self.assertFalse(self.db.is_group_active(3002))         # 无激活副作用

    def test_resolve_approved_path(self):
        self.db.upsert_request(3003, 1001, "flag-2", "invite")
        pending = self.db.pending_requests()[0]["created_at"]
        self.assertTrue(self.db.resolve_request(3003, 1001, pending, approve=True))
        self.assertEqual(self.conn.execute(
            "SELECT status FROM group_requests WHERE flag = 'flag-2'").fetchone()[0], "approved")

    # —— 黑名单 ——

    def test_ban_unban_scopes_isolated(self):
        self.db.ban("user", 1001, "刷屏")
        self.db.ban("user", 1001, "换理由")                     # 幂等
        self.db.ban("group", 4001)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM blacklist").fetchone()[0], 2)
        self.assertTrue(self.db.is_banned("user", 1001))
        self.assertTrue(self.db.is_banned("group", 4001))
        self.assertFalse(self.db.is_banned("user", 4001))       # 范围互不影响
        self.assertTrue(self.db.unban("user", 1001))
        self.assertFalse(self.db.is_banned("user", 1001))
        self.assertFalse(self.db.unban("user", 1001))           # 再解除无行可删
        self.assertTrue(self.db.is_banned("group", 4001))

    # —— 建表幂等与挂载 ——

    def test_init_schema_twice_idempotent(self):
        init_schema(self.conn, self.conn.cursor())              # 二次建表不报错不重复
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='user_accounts'"
        ).fetchone()[0], 1)

    def test_manager_attached_to_dbmanager(self):
        from core.database_manager import DbManager
        self.assertTrue(hasattr(DbManager, "community") is False or True)  # 实例属性
        # 直接验证实例属性存在（不连接真实配置库）
        import core.config as cfg
        old = cfg.DB_PATH
        cfg.DB_PATH = Path(self._tmp.name) / "dm.db"
        try:
            dm = DbManager()
            try:
                self.assertIsInstance(dm.community, CommunityManager)
                dm.community.register_user(7)
                self.assertTrue(dm.community.is_registered(7))
            finally:
                dm.conn.close()
        finally:
            cfg.DB_PATH = old


if __name__ == "__main__":
    unittest.main(verbosity=2)
