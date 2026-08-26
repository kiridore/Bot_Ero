"""积分原子性回归：adjust/spend 单语句原子、并发不丢更新、余额不可为负。
运行: pytest test/test_points_atomic.py
"""
import os
import sys
import sqlite3
import threading
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import test.helper  # noqa: F401  桩掉 core.api.WS_APP，必须在导入插件前执行

from core.db._base import init_schema
from core.db.points import PointsManager
from core.utils import add_user_point

DB_PATH = "/tmp/test_points_atomic.db"


class _Db:
    """add_user_point 只用 db.points，包一层即可独立于完整 DbManager。"""
    def __init__(self, pm):
        self.points = pm


class TestPointsAtomic(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        self.conn = sqlite3.connect(DB_PATH)
        init_schema(self.conn, self.conn.cursor())
        self.pm = PointsManager(self.conn)
        self.db = _Db(self.pm)

    def tearDown(self):
        self.conn.close()

    def test_spend_conditional(self):
        self.pm.set("10001", 3)
        self.assertTrue(self.pm.spend("10001", 2))
        self.assertFalse(self.pm.spend("10001", 2))  # 余额 1 不足
        self.assertEqual(self.pm.get("10001"), 1)    # 失败不改动

    def test_spend_missing_row_is_insufficient(self):
        self.assertFalse(self.pm.spend("99999", 1))  # 无行 = 0 分，拒绝而非报错

    def test_add_user_point_is_atomic_under_threads(self):
        # add_user_point 必须是单语句原子：20 线程各 10 次×+10，最终严格等于 2000
        add_user_point(self.db, "10002", 0)
        # check_same_thread=False：每个连接仅由其 worker 线程使用，但创建于主线程
        conns = [sqlite3.connect(DB_PATH, check_same_thread=False) for _ in range(20)]
        for c in conns:
            c.execute("PRAGMA busy_timeout=5000")
        dbs = [_Db(PointsManager(c)) for c in conns]

        def worker(db):
            for _ in range(10):
                add_user_point(db, "10002", 10)

        threads = [threading.Thread(target=worker, args=(db,)) for db in dbs]
        [t.start() for t in threads]
        [t.join() for t in threads]
        [c.close() for c in conns]
        self.assertEqual(self.pm.get("10002"), 2000)

    def test_concurrent_spend_never_negative(self):
        # 并发 50 次 spend(1)，余额 10：成功次数必须恰好 10，余额 0
        add_user_point(self.db, "10003", 10)
        conns = [sqlite3.connect(DB_PATH, check_same_thread=False) for _ in range(10)]
        for c in conns:
            c.execute("PRAGMA busy_timeout=5000")
        pms = [PointsManager(c) for c in conns]
        results = []

        def worker(pm):
            for _ in range(5):
                results.append(pm.spend("10003", 1))

        threads = [threading.Thread(target=worker, args=(pm,)) for pm in pms]
        [t.start() for t in threads]
        [t.join() for t in threads]
        [c.close() for c in conns]
        self.assertEqual(results.count(True), 10)
        self.assertEqual(self.pm.get("10003"), 0)


if __name__ == "__main__":
    unittest.main()
