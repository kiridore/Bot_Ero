"""网页打卡上传时间线回归：网页打卡 emit source=checkin 事件（data.private=True）、
落库 is_private=1、缩略图预生成、dedup_key 与 bot 侧同前缀。
运行: pytest test/test_web_checkin_emit.py
"""
import os
import sqlite3
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import test.helper  # noqa: F401  统一桩掉 core.api 全局（导入插件的既有模式）

from core import config as core_config
from core.db._base import init_schema
from core.db.checkin import CheckinManager
from core.db.points import PointsManager
from core.db.shop import ShopManager
from webapp.profile import checkin_service

DB_PATH = "/tmp/test_web_checkin_emit.db"
IMAGE_ROOT = Path("/tmp/test_web_checkin_images")


class _Db:
    """perform_checkin 依赖的三管理器（真实 manager + 临时库）。"""

    def __init__(self, conn):
        self.checkin = CheckinManager(conn)
        self.points = PointsManager(conn)
        self.shop = ShopManager(conn)


class TestWebCheckinEmit(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        self.conn = sqlite3.connect(DB_PATH)
        init_schema(self.conn, self.conn.cursor())
        self.db = _Db(self.conn)

        # 图片目录：预置 1 张图片文件（内容随意——缩略图函数被桩掉）
        IMAGE_ROOT.mkdir(parents=True, exist_ok=True)
        user_dir = IMAGE_ROOT / "555666"
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "webfake0.jpg").write_bytes(b"fake-jpeg-bytes")

        self._emitted = []
        self._thumbs = []

        # 桩 checkin_service 模块命名空间（实现须以模块级名引入这些依赖）
        self._orig = {name: getattr(checkin_service, name, None)
                      for name in ("DbManager", "_load_title_helpers")}
        self._has_attr = {name: hasattr(checkin_service, name)
                          for name in ("emit_event", "ensure_thumbnail")}
        checkin_service.DbManager = lambda: self.db
        checkin_service._load_title_helpers = lambda: (None, None)
        checkin_service.emit_event = lambda **kw: self._emitted.append(kw)
        checkin_service.ensure_thumbnail = lambda src: self._thumbs.append(Path(src))
        self._orig_image_root = core_config.IMAGE_ROOT
        core_config.IMAGE_ROOT = IMAGE_ROOT

        self.addCleanup(self._restore)

    def _restore(self):
        for name, val in self._orig.items():
            if val is not None:
                setattr(checkin_service, name, val)
        for name, had in self._has_attr.items():
            if not had and hasattr(checkin_service, name):
                delattr(checkin_service, name)
        core_config.IMAGE_ROOT = self._orig_image_root
        self.conn.close()

    def test_web_checkin_emits_private_timeline_event(self):
        result = checkin_service.perform_checkin("555666", ["webfake0.jpg"])

        self.assertTrue(result["success"])
        # 事件：恰一条、结构对齐 bot 侧
        self.assertEqual(len(self._emitted), 1)
        ev = self._emitted[0]
        self.assertEqual(ev["source"], "checkin")
        self.assertEqual(ev["title"], "{id:555666} 完成打卡")
        self.assertEqual(ev["description"], "本周第 1 次")
        self.assertTrue(ev["data"]["private"])
        self.assertEqual(ev["data"]["images"], ["/thumb/555666/webfake0.jpg"])
        self.assertTrue(ev["dedup_key"].startswith("checkin:555666:"))
        self.assertIn(":web-", ev["dedup_key"])
        # 落库：网页打卡标记私聊
        flag = self.conn.execute(
            "SELECT is_private FROM checkin_records WHERE user_id = ?", ("555666",)
        ).fetchone()
        self.assertIsNotNone(flag)
        self.assertEqual(flag[0], 1)
        # 缩略图：对已存在文件预生成（首屏即可用 /thumb/ URL）
        self.assertEqual(self._thumbs, [IMAGE_ROOT / "555666" / "webfake0.jpg"])


if __name__ == "__main__":
    unittest.main()
