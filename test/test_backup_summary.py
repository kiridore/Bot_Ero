"""数据备份日报文案测试：仅显示数据校验成功率，不足 100% 时 @ 超管。

运行: pytest test/test_backup_summary.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.base import SUPER_USER
from plugins.backup import BackupPlugin
from test.helper import MockApiWrapper, make_group_message


def _plugin():
    p = BackupPlugin(make_group_message("meta"))
    p.api = MockApiWrapper(make_group_message("meta"))
    return p


def _run(statuses):
    plugin = _plugin()
    rows = [(i, 100 + i, None, f"img{i}.jpg") for i in range(len(statuses))]
    plugin.dbmanager = SimpleNamespace(checkin=SimpleNamespace(all_records=lambda: rows))
    with patch("plugins.backup.ensure_checkin_image", side_effect=statuses):
        plugin.handle()
    return plugin.api.sent_messages


class TestBackupSummary(unittest.TestCase):
    def test_all_pass_single_rate_message(self):
        msgs = _run(["exists", "downloaded", "remedy"])
        self.assertEqual(len(msgs), 1)
        node = msgs[0][1][0]
        self.assertEqual(node["type"], "text")
        self.assertEqual(node["data"]["text"], "数据校验成功率：100.00%")

    def test_below_100_ats_super_user_first(self):
        msgs = _run(["exists", "error"])
        self.assertEqual(len(msgs), 1)
        first = msgs[0][1][0]
        self.assertEqual(first["type"], "at")
        self.assertEqual(first["data"]["qq"], SUPER_USER[0])
        self.assertEqual(msgs[0][1][1]["data"]["text"], "数据校验成功率：50.00%")

    def test_empty_records_is_100_no_at(self):
        msgs = _run([])
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0][1][0]["type"], "text")
        self.assertEqual(msgs[0][1][0]["data"]["text"], "数据校验成功率：100.00%")


if __name__ == "__main__":
    unittest.main()
