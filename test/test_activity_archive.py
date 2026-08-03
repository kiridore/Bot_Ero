"""测试活动归档。
运行: python test/test_activity_archive.py
"""
import os
import sys
import json
import shutil
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import core.context as context
from plugins.activity import archive

TEST_ROOT = "/tmp/test_activity_archive"


def _member(uid, nick, seq, status="done", content=None, images=None):
    return {
        "user_id": uid, "nickname": nick, "seq": seq, "status": status,
        "next_user_id": None, "received_at": "2026-09-01 00:00:00",
        "submitted_at": "2026-09-02 00:00:00", "content": content, "images": images,
    }


class TestArchive(unittest.TestCase):
    def setUp(self):
        context.python_data_path = TEST_ROOT
        if os.path.exists(TEST_ROOT):
            shutil.rmtree(TEST_ROOT)

    def test_archive_relay(self):
        act = {"id": 1, "type": "relay", "title": "端午接龙", "theme": "粽子",
               "group_id": 296470819, "created_at": "2026-09-01 00:00:00",
               "finished_at": "2026-09-03 00:00:00", "status": "finished"}
        members = [
            _member("1", "A", 1, content="第一章", images='["img_1_1.jpg"]'),
            _member("2", "B", 2, content="第二章", images=None),
        ]
        archive.archive_activity(act, members)
        d = archive.archive_dir(1)
        self.assertTrue(os.path.isfile(f"{d}/meta.json"))
        self.assertTrue(os.path.isfile(f"{d}/relay.md"))
        with open(f"{d}/relay.md", encoding="utf-8") as f:
            md = f.read()
        self.assertIn("端午接龙", md)
        self.assertIn("A", md)
        self.assertIn("第一章", md)
        self.assertIn("imgs/img_1_1.jpg", md)
        self.assertFalse(os.path.exists(f"{d}/match.md"))
        with open(f"{d}/meta.json", encoding="utf-8") as f:
            meta = json.load(f)
        self.assertEqual(meta["id"], 1)
        self.assertEqual(meta["members"][1]["nickname"], "B")

    def test_archive_match_marks_missed(self):
        act = {"id": 2, "type": "match", "title": "中秋", "theme": None,
               "group_id": 1, "created_at": "2026-09-01 00:00:00",
               "finished_at": "2026-09-10 00:00:00", "status": "finished"}
        members = [
            _member("1", "A", 1, content="给下家的礼物", images=None),
            _member("2", "B", 2, status="missed", content=None, images=None),
        ]
        archive.archive_activity(act, members)
        with open(f"{archive.archive_dir(2)}/match.md", encoding="utf-8") as f:
            md = f.read()
        self.assertIn("给下家的礼物", md)
        self.assertIn("B", md)
        self.assertIn("未提交", md)


if __name__ == "__main__":
    unittest.main()
