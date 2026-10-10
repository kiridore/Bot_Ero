"""/发金币 权限统一：仅超级用户（grant-points-superuser，AC1）。"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import config
from core.database_manager import DbManager
from core.event import Event
from plugins.grant_points_all import GrantPointsAllPlugin
from test.helper import make_group_message, make_private_message


class GrantPointsPermissionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = config.DB_PATH
        config.DB_PATH = Path(self._tmp.name) / "grant.db"
        self.db = DbManager()

    def tearDown(self):
        self.db.conn.close()
        config.DB_PATH = self._old
        self._tmp.cleanup()

    def _plugin(self, raw):
        p = GrantPointsAllPlugin.__new__(GrantPointsAllPlugin)
        p.bot_event = Event(raw)
        p.dbmanager = self.db
        p.api = Mock()
        p.operation = Mock()
        p.operation.enabled = {"grant_points_all": True}
        return p

    def _match(self, raw):
        p = self._plugin(raw)
        p.match("message")  # CommandPlugin 填充 self.args
        return p

    def _group_raw(self, role="member", uid=123456):
        raw = make_group_message("/发金币 5", user_id=uid)
        raw["sender"]["role"] = role
        return raw

    def test_group_admin_and_owner_do_not_match(self):
        for role in ("admin", "owner"):
            self.assertFalse(self._plugin(self._group_raw(role)).match("message"), role)

    def test_super_user_matches_in_group_and_private(self):
        raw = self._group_raw(uid=int(config.SUPER_USER[0]))
        self.assertTrue(self._plugin(raw).match("message"))
        raw_private = make_private_message("/发金币 5",
                                           user_id=int(config.SUPER_USER[0]))
        self.assertTrue(self._plugin(raw_private).match("message"))

    def test_ordinary_member_does_not_match(self):
        self.assertFalse(self._plugin(self._group_raw()).match("message"))

    def test_super_user_still_grants(self):
        raw = self._group_raw(uid=int(config.SUPER_USER[0]))
        self.db.points.set(42, 0)
        p = self._match(raw)
        p.handle()
        self.assertEqual(p.args, ["5"])
        self.assertEqual(self.db.points.get(42), 5)  # 全员 +5


if __name__ == "__main__":
    unittest.main(verbosity=2)
