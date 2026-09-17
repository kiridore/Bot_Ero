"""议事厅过期投票自动关闭的时间线事件 actor 测试。

背景：forum_notify 自动关闭过期投票时曾用 actor_qq="0" 冒充系统事件，
QQ 0 无法解析昵称/头像，时间线上显示「0」且无头像。系统事件 actor
契约与 weekly_report / activity 一致 = bot 本体 BOT_QQ。

运行: pytest test/test_forum_notify_poll_close.py
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.base import BOT_QQ
from core.config import GROUP_ID
from plugins.forum_notify import ForumNotifyPlugin
import plugins.forum_notify as forum_notify
from test.helper import MockApiWrapper, make_group_message


class TestExpiredPollCloseEvent(unittest.TestCase):
    def setUp(self):
        ForumNotifyPlugin._last_run_minute.clear()
        self.plugin = ForumNotifyPlugin(make_group_message("meta"))
        self.plugin.api = MockApiWrapper(make_group_message("meta"))
        self.db = self.plugin.dbmanager
        deadline = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        self.post_id = self.db.forum.create_post(
            str(GROUP_ID), "poll", "周末桌游投票", "",
            polls=[{"title": "去吗", "allow_multi": False, "options": ["去", "不去"]}],
            poll_deadline=deadline,
        )
        self._emit = patch.object(forum_notify, "emit_event")
        self.mock_emit = self._emit.start()

    def tearDown(self):
        self._emit.stop()
        ForumNotifyPlugin._last_run_minute.clear()
        for table in ("forum_poll_options", "forum_polls", "forum_posts"):
            self.db.cur.execute(f"DELETE FROM {table}")  # 表名白名单字面量，无注入面
        self.db.conn.commit()

    def test_expired_poll_close_event_actor_is_bot(self):
        self.plugin.handle()
        self.mock_emit.assert_called_once()
        kwargs = self.mock_emit.call_args.kwargs
        self.assertEqual(kwargs["actor_id"], BOT_QQ)
        self.assertEqual(kwargs["actor_qq"], BOT_QQ)
        self.assertEqual(kwargs["dedup_key"], f"forum_poll_close:{self.post_id}")
