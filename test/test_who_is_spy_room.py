"""谁是卧底房间退出回归：waiting 阶段非房主退出不崩溃。
运行: pytest test/test_who_is_spy_room.py
"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import test.helper  # noqa: F401

import core.context as context
from plugins.who_is_spy import room


def _make_room(room_id):
    context.game_rooms[room_id] = {
        "phase": "waiting",
        "creator_id": "111",
        "players": {
            "111": {"alias": "1号", "alive": True},
            "222": {"alias": "2号", "alive": True},
        },
    }


class TestRemovePlayer(unittest.TestCase):
    def tearDown(self):
        context.game_rooms.clear()

    def test_member_exit_waiting_no_crash(self):
        _make_room("T001")
        msg = room.remove_player("T001", 222)  # 修复前此处 UnboundLocalError
        self.assertEqual(msg, "已退出房间 T001")
        self.assertIn("111", context.game_rooms["T001"]["players"])

    def test_creator_exit_transfers_room(self):
        _make_room("T002")
        msg = room.remove_player("T002", 111)
        self.assertIn("房主已转移给 1号", msg)
        self.assertEqual(context.game_rooms["T002"]["creator_id"], "222")

    def test_last_player_disbands(self):
        _make_room("T003")
        room.remove_player("T003", 222)
        msg = room.remove_player("T003", 111)
        self.assertEqual(msg, "房间已解散")
        self.assertNotIn("T003", context.game_rooms)


if __name__ == "__main__":
    unittest.main()
