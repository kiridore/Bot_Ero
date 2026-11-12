"""功能包权限：群主只能给自己所在群开启白名单包，其余仍限超管。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import config
from core.feature_packs import FEATURE_PACKS
from plugins.group_manager import GroupManagerPlugin, OWNER_PACKS
from test.helper import MockApiWrapper

GROUP_ID = 296470819
OWNER_ID = 111
ADMIN_ID = 222


def _event(text: str, user_id=OWNER_ID, role="owner", group_id=GROUP_ID) -> dict:
    return {
        "post_type": "message",
        "message_type": "group",
        "user_id": user_id,
        "group_id": group_id,
        "message": [{"type": "text", "data": {"text": text}}],
        "sender": {"user_id": user_id, "nickname": "群主", "role": role},
        "time": 0,
        "message_id": -1,
    }


def _run(text: str, **kwargs) -> str:
    ctx = _event(text, **kwargs)
    plugin = GroupManagerPlugin(ctx)
    plugin.api = MockApiWrapper(ctx)
    assert plugin.match("message"), "指令未匹配"
    plugin.handle()
    assert plugin.api.sent_messages, "未发送任何消息"
    return plugin.api.sent_messages[-1][1][0]["data"]["text"]


class OwnerPackTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / "t.db"
        patcher = patch("core.config.DB_PATH", db)
        patcher.start()
        self.addCleanup(patcher.stop)
        from core.database_manager import init_schema
        import sqlite3
        conn = sqlite3.connect(db)
        init_schema(conn, conn.cursor())
        conn.commit()
        conn.close()
        self.db = db

    def _enabled(self) -> set[str]:
        import sqlite3
        conn = sqlite3.connect(self.db)
        rows = conn.execute(
            "SELECT plugin_name FROM group_plugin_config WHERE group_id = ?", (GROUP_ID,)).fetchall()
        conn.close()
        return {r[0] for r in rows}

    def test_pack_includes_vitals(self):
        self.assertIn("trpg_vitals", FEATURE_PACKS["跑团"]["plugins"])

    def test_owner_can_open_trpg_pack(self):
        out = _run("/功能包 跑团")
        self.assertIn("已开启功能包「跑团」", out)
        enabled = self._enabled()
        for key in ("trpg_dice", "trpg_session", "trpg_char", "trpg_vitals"):
            self.assertIn(key, enabled)

    def test_owner_can_open_base_pack(self):
        _run("/功能包 基础包")
        self.assertIn("checkin", self._enabled())

    def test_owner_cannot_open_other_pack(self):
        out = _run("/功能包 休闲娱乐")
        self.assertIn("群主只能开启", out)
        self.assertEqual(self._enabled(), set())

    def test_owner_cannot_disable(self):
        _run("/功能包 跑团")
        out = _run("/功能包 跑团 off")
        self.assertIn("只能开启", out)
        self.assertIn("trpg_dice", self._enabled())

    def test_owner_cannot_target_other_group(self):
        out = _run("/功能包 跑团 987654")
        self.assertIn("只能操作自己所在的群", out)
        self.assertEqual(self._enabled(), set())

    def test_owner_cannot_manage_single_plugin(self):
        out = _run("/插件 trpg_dice")
        self.assertIn("只能开启功能包", out)

    def test_group_admin_is_not_owner(self):
        out = _run("/功能包 跑团", user_id=ADMIN_ID, role="admin")
        self.assertIn("仅超级用户", out)

    def test_super_user_full_access(self):
        with patch("plugins.group_manager.GroupManagerPlugin.super_user", return_value=True):
            out = _run("/功能包 休闲娱乐", user_id=999, role="member")
        self.assertIn("开启功能包「休闲娱乐」", out)

    def test_owner_packs_constant(self):
        self.assertEqual(tuple(OWNER_PACKS), ("基础包", "跑团"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
