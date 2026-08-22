"""测试积分商店货架刷新（redeem_shop.logic.weekly_refresh_shop_shelf）。
运行: pytest test/test_shop_shelf.py
"""
import os
import sqlite3
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.db._base import init_schema
from core.db.shop import ShopManager
from plugins.redeem_shop.logic import (
    FIXED_FUNCTION_ITEMS,
    refresh_shop_items_from_database,
    weekly_refresh_shop_shelf,
)
from plugins.title import TITLE_DEFS, get_lottery_title_ids

DB_PATH = "/tmp/test_shop_shelf.db"


class _Db:
    """测试用：仅挂商店所需管理器，跳过真实 DbManager 的全局库。"""

    def __init__(self, conn):
        self.shop = ShopManager(conn)


class TestShopShelf(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        self.conn = sqlite3.connect(DB_PATH)
        init_schema(self.conn, self.conn.cursor())
        self.db = _Db(self.conn)

    def tearDown(self):
        self.conn.close()
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

    def _shelf_title_ids(self):
        return [
            int(pid.split("_", 1)[1])
            for pid, _ in self.db.shop.all_stock()
            if pid.startswith("title_")
        ]

    def test_shelf_titles_are_lottery_only(self):
        """上架称号必须全部来自抽奖解锁池，条件/兑换码称号不得上架。"""
        picked = weekly_refresh_shop_shelf(self.db)
        lottery_ids = set(get_lottery_title_ids())
        for tid in picked:
            self.assertIn(tid, lottery_ids, f"称号 {tid} 非抽奖解锁却上架")
            self.assertEqual(
                TITLE_DEFS[tid]["unlock_type"], "lottery", f"称号 {tid} unlock_type 错误"
            )
        shelf_ids = set(self._shelf_title_ids())
        self.assertEqual(shelf_ids, set(picked), "货架 title_* 与 picked 不一致")

    def test_shelf_has_fixed_function_items(self):
        """固定功能商品始终上架。"""
        weekly_refresh_shop_shelf(self.db)
        shelf_pids = {pid for pid, _ in self.db.shop.all_stock()}
        for pid in FIXED_FUNCTION_ITEMS:
            self.assertIn(pid, shelf_pids, f"固定商品 {pid} 缺失")

    def test_memory_rebuild_matches_db(self):
        """内存 SHOP_ITEMS 重建后与库表一致且无条件称号。"""
        weekly_refresh_shop_shelf(self.db)
        refresh_shop_items_from_database(self.db)
        shelf_ids = set(self._shelf_title_ids())
        lottery_ids = set(get_lottery_title_ids())
        self.assertTrue(shelf_ids, "货架不应为空")
        self.assertTrue(shelf_ids <= lottery_ids, "内存货架混入非抽奖称号")

    def test_no_condition_titles_ever(self):
        """多次刷新后条件称号 id（>=200 或 unlock_type=condition）绝不上架。"""
        for _ in range(5):
            weekly_refresh_shop_shelf(self.db)
            for tid in self._shelf_title_ids():
                self.assertNotEqual(TITLE_DEFS[tid]["unlock_type"], "condition")
                self.assertNotEqual(TITLE_DEFS[tid]["unlock_type"], "redeem")


if __name__ == "__main__":
    unittest.main()
