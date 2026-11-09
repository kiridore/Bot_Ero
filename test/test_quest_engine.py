"""周常引擎冒烟（社区版 T0.5 迁入新家 plugins/weekly_quest/engine.py）：trigger 发奖 / rollback 撤奖 / 新家符号。"""
import sys
import unittest

from core.database_manager import DbManager
from plugins.weekly_quest import engine

UID = 999901


class TestQuestEngine(unittest.TestCase):
    def setUp(self):
        db = DbManager()
        db.conn.execute("DELETE FROM checkin_records WHERE user_id = ?", (UID,))
        db.conn.execute("DELETE FROM quest_progress WHERE user_id = ?", (UID,))
        db.conn.execute("DELETE FROM plugin_reward_records WHERE user_id = ?", (UID,))
        db.conn.execute("DELETE FROM quest_completion_stats WHERE user_id = ?", (UID,))
        db.conn.execute("DELETE FROM quest_weekly_clears WHERE user_id = ?", (UID,))
        db.conn.execute("DELETE FROM user_assets WHERE user_id = ?", (UID,))
        db.conn.commit()
        self.db = db
        self.assertEqual(self.db.points.get(UID), 0)

    def tearDown(self):
        self.db.conn.close()

    def test_engine_symbols_live_in_new_home(self):
        for sym in ("QUEST_DEFS", "get_quest_week_key", "on_quest_trigger", "on_quest_rollback"):
            self.assertTrue(hasattr(engine, sym), sym)

    def test_trigger_claims_reached_quest_and_pays(self):
        self.db.checkin.insert(UID, images=["t.png"], message_id=1001)
        completed = engine.on_quest_trigger(self.db, UID, "checkin")
        # 仅 goal=1 的任务 1 达标（任务 2/3 goal 3/7）
        self.assertEqual(completed, [{"name": "打个卡先", "reward": 1}])
        self.assertEqual(self.db.points.get(UID), 1)

    def test_rollback_revokes_when_below_goal(self):
        self.db.checkin.insert(UID, images=["t.png"], message_id=1001)
        engine.on_quest_trigger(self.db, UID, "checkin")
        self.db.checkin.delete_by_msg(UID, 1001)
        revoked = engine.on_quest_rollback(self.db, UID, "checkin")
        self.assertEqual([q["id"] for q in revoked], [1])
        self.assertEqual(self.db.points.get(UID), 0)


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=2))
