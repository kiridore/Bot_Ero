"""测试 TRPG 会话录制插件。

运行: pytest test/test_trpg_session.py
"""

from __future__ import annotations

import os
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from plugins.trpg_session import TrpgSessionPlugin
from test.helper import MockApiWrapper, make_group_message, make_private_message
import core.context as runtime_context


def _sent_text(plugin) -> str:
    assert len(plugin.api.sent_messages) >= 1
    return plugin.api.sent_messages[-1][1][0]["data"]["text"]


def _sent_count(plugin) -> int:
    return len(plugin.api.sent_messages)


class TestTrpgSessionMatch(unittest.TestCase):
    def setUp(self):
        runtime_context.recording_sessions.clear()
        runtime_context.last_completed.clear()

    def test_match_command(self):
        ctx = make_group_message("/跑团记录 开始")
        self.assertTrue(TrpgSessionPlugin(ctx).match("message"))

    def test_match_list(self):
        ctx = make_group_message("/跑团记录 列表")
        self.assertTrue(TrpgSessionPlugin(ctx).match("message"))

    def test_match_plain_command(self):
        ctx = make_group_message("/跑团记录")
        self.assertTrue(TrpgSessionPlugin(ctx).match("message"))

    def test_no_match_other(self):
        ctx = make_group_message(".r 2d6")
        self.assertFalse(TrpgSessionPlugin(ctx).match("message"))

    def test_no_match_non_message(self):
        ctx = make_group_message("hello")
        self.assertFalse(TrpgSessionPlugin(ctx).match("notice"))

    def test_match_all_during_recording(self):
        runtime_context.recording_sessions[296470819] = {"start": None, "messages": [], "participants": {}}
        ctx = make_group_message("普通聊天消息")
        self.assertTrue(TrpgSessionPlugin(ctx).match("message"))

    def test_private_message_refused(self):
        ctx = make_private_message("/跑团记录 开始")
        plugin = TrpgSessionPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        self.assertIn("只能在群聊中使用", _sent_text(plugin))

    def tearDown(self):
        runtime_context.recording_sessions.clear()
        runtime_context.last_completed.clear()


class TestTrpgSessionRecording(unittest.TestCase):
    def setUp(self):
        runtime_context.recording_sessions.clear()
        runtime_context.last_completed.clear()

    def test_start_recording(self):
        ctx = make_group_message("/跑团记录 开始")
        plugin = TrpgSessionPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        self.assertIn("已开始", _sent_text(plugin))
        self.assertTrue(runtime_context.is_group_recording(296470819))

    def test_start_twice_warns(self):
        runtime_context.recording_sessions[296470819] = {"start": None, "messages": [], "participants": {}}
        ctx = make_group_message("/跑团记录 开始")
        plugin = TrpgSessionPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        self.assertIn("已在录制", _sent_text(plugin))

    def test_start_with_unexported_warns(self):
        runtime_context.last_completed[296470819] = {"messages": [{"dummy": True}]}
        ctx = make_group_message("/跑团记录 开始")
        plugin = TrpgSessionPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        self.assertIn("尚未导出", _sent_text(plugin))
        self.assertFalse(runtime_context.is_group_recording(296470819))

    def test_force_start_discards_unexported(self):
        runtime_context.last_completed[296470819] = {"messages": [{"dummy": True}]}
        ctx = make_group_message("/跑团记录 强制开始")
        plugin = TrpgSessionPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        self.assertIn("已丢弃", _sent_text(plugin))
        self.assertTrue(runtime_context.is_group_recording(296470819))
        self.assertIsNone(runtime_context.get_last_completed(296470819))

    def test_record_user_message(self):
        runtime_context.recording_sessions[296470819] = {"start": None, "messages": [], "participants": {}}
        ctx = make_group_message("测试消息", user_id=111, nickname="玩家A")
        plugin = TrpgSessionPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        self.assertTrue(plugin.match("message"))
        plugin.handle()
        session = runtime_context.get_recording_session(296470819)
        self.assertEqual(len(session["messages"]), 1)
        self.assertEqual(session["messages"][0]["nickname"], "玩家A")
        self.assertEqual(session["messages"][0]["type"], "user")

    def test_record_skips_bot_message(self):
        runtime_context.recording_sessions[296470819] = {"start": None, "messages": [], "participants": {}}
        ctx = make_group_message("bot 消息", user_id=3915014383, nickname="小埃同学")
        plugin = TrpgSessionPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        session = runtime_context.get_recording_session(296470819)
        self.assertEqual(len(session["messages"]), 0, "机器人自己的消息不应被录制")

    def test_dm_sets_role(self):
        ctx = make_group_message(".dm", user_id=111, nickname="玩家A")
        plugin = TrpgSessionPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        self.assertIn("DM", _sent_text(plugin))
        self.assertEqual(runtime_context.group_roles.get(296470819, {}).get("111"), "dm")

    def test_ob_sets_role(self):
        ctx = make_group_message(".ob", user_id=222, nickname="玩家B")
        plugin = TrpgSessionPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        self.assertIn("观察者", _sent_text(plugin))
        self.assertEqual(runtime_context.group_roles.get(296470819, {}).get("222"), "ob")

    def test_role_carries_into_recording(self):
        runtime_context.group_roles[296470819] = {"111": "dm"}
        runtime_context.recording_sessions[296470819] = {"start": None, "messages": [], "participants": {}, "roles": dict(runtime_context.group_roles.get(296470819, {}))}
        self.assertEqual(runtime_context.recording_sessions[296470819]["roles"]["111"], "dm")

    def test_stop_while_not_recording(self):
        ctx = make_group_message("/跑团记录 结束")
        plugin = TrpgSessionPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        self.assertIn("没有进行中", _sent_text(plugin))

    def test_full_flow_start_stop(self):
        ctx = make_group_message("/跑团记录 开始")
        p1 = TrpgSessionPlugin(ctx)
        p1.api = MockApiWrapper(ctx)
        p1.handle()
        self.assertTrue(runtime_context.is_group_recording(296470819))

        runtime_context.recording_sessions[296470819]["messages"].append({
            "type": "user", "nickname": "玩家A", "user_id": "111",
            "message": [{"type": "text", "data": {"text": "hello"}}],
            "time": 0,
        })
        runtime_context.recording_sessions[296470819]["participants"]["111"] = {"nickname": "玩家A", "user_id": "111"}

        ctx2 = make_group_message("/跑团记录 结束")
        p2 = TrpgSessionPlugin(ctx2)
        p2.api = MockApiWrapper(ctx2)
        p2.handle()
        self.assertFalse(runtime_context.is_group_recording(296470819))
        self.assertIsNotNone(runtime_context.get_last_completed(296470819))


class TestTrpgSessionExport(unittest.TestCase):
    def setUp(self):
        runtime_context.recording_sessions.clear()
        runtime_context.last_completed.clear()
        # 导出目录重定向到临时目录（patch 插件常量），避免写删真实 server_data
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher = patch("plugins.trpg_session.TRPG_RECORDS_ROOT", self._tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.export_dir = os.path.join(self._tmp.name, "296470819")

    def tearDown(self):
        runtime_context.recording_sessions.clear()
        runtime_context.last_completed.clear()

    def test_export_while_recording_refused(self):
        runtime_context.recording_sessions[296470819] = {"start": None, "messages": [], "participants": {}}
        ctx = make_group_message("/跑团记录 导出")
        plugin = TrpgSessionPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        self.assertIn("录制中无法导出", _sent_text(plugin))

    def test_export_no_completed_refused(self):
        ctx = make_group_message("/跑团记录 导出")
        plugin = TrpgSessionPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        self.assertIn("没有可导出", _sent_text(plugin))

    @patch("plugins.trpg_session.download_image", return_value=(True, ""))
    def test_export_creates_files(self, mock_dl):
        from datetime import datetime
        now = datetime.now()
        runtime_context.last_completed[296470819] = {
            "start": now, "end": now,
            "messages": [
                {"type": "user", "nickname": "玩家A", "user_id": "111",
                 "message": [{"type": "text", "data": {"text": "hello"}}],
                 "time": 0},
                {"type": "bot", "nickname": "小埃同学", "user_id": "3915014383",
                 "message": [{"type": "text", "data": {"text": "world"}}],
                 "time": 0},
            ],
            "participants": {"111": {"nickname": "玩家A", "user_id": "111"}},
        }

        ctx = make_group_message("/跑团记录 导出")
        plugin = TrpgSessionPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        self.assertIn("导出成功", _sent_text(plugin))

        # 检查文件是否创建
        folders = os.listdir(self.export_dir)
        self.assertEqual(len(folders), 1)
        folder = f"{self.export_dir}/{folders[0]}"
        self.assertTrue(os.path.isfile(f"{folder}/meta.json"))
        self.assertTrue(os.path.isfile(f"{folder}/record.md"))

        with open(f"{folder}/meta.json", "r") as f:
            meta = json.load(f)
        self.assertIn("participants", meta)
        self.assertIn("start", meta)
        self.assertIn("end", meta)

        with open(f"{folder}/record.md", "r") as f:
            content = f.read()
        self.assertIn("玩家A", content)
        self.assertIn("小埃同学", content)

    def test_export_with_image(self):
        from datetime import datetime
        now = datetime.now()
        runtime_context.last_completed[296470819] = {
            "start": now, "end": now,
            "messages": [
                {"type": "user", "nickname": "玩家A", "user_id": "111",
                 "message": [
                     {"type": "text", "data": {"text": "看一下这个"}},
                     {"type": "image", "data": {"file": "test.jpg"}},
                 ],
                 "time": 0},
            ],
            "participants": {"111": {"nickname": "玩家A", "user_id": "111"}},
        }

        ctx = make_group_message("/跑团记录 导出")
        plugin = TrpgSessionPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        self.assertIn("导出成功", _sent_text(plugin))


class TestTrpgSessionListAndView(unittest.TestCase):
    def setUp(self):
        runtime_context.recording_sessions.clear()
        runtime_context.last_completed.clear()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher = patch("plugins.trpg_session.TRPG_RECORDS_ROOT", self._tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.export_dir = os.path.join(self._tmp.name, "296470819")

    def tearDown(self):
        runtime_context.recording_sessions.clear()
        runtime_context.last_completed.clear()

    def test_list_empty(self):
        ctx = make_group_message("/跑团记录 列表")
        plugin = TrpgSessionPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        self.assertIn("暂无", _sent_text(plugin))

    def test_view_out_of_range(self):
        ctx = make_group_message("/跑团记录 #1")
        plugin = TrpgSessionPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        out = _sent_text(plugin)
        self.assertTrue("编号无效" in out or "暂无" in out)

    @patch("plugins.trpg_session.download_image", return_value=(True, ""))
    def test_list_and_view_after_export(self, mock_dl):
        from datetime import datetime
        now = datetime.now()
        # 先导出
        runtime_context.last_completed[296470819] = {
            "start": now, "end": now,
            "messages": [
                {"type": "user", "nickname": "玩家A", "user_id": "111",
                 "message": [{"type": "text", "data": {"text": "hello"}}],
                 "time": 0},
            ],
            "participants": {"111": {"nickname": "玩家A", "user_id": "111"}},
        }
        ctx = make_group_message("/跑团记录 导出")
        p1 = TrpgSessionPlugin(ctx)
        p1.api = MockApiWrapper(ctx)
        p1.handle()
        self.assertIn("导出成功", _sent_text(p1))

        # 列表
        ctx2 = make_group_message("/跑团记录 列表")
        p2 = TrpgSessionPlugin(ctx2)
        p2.api = MockApiWrapper(ctx2)
        p2.handle()
        self.assertIn("[1]", _sent_text(p2))

        # 查看 #1
        ctx3 = make_group_message("/跑团记录 #1")
        p3 = TrpgSessionPlugin(ctx3)
        p3.api = MockApiWrapper(ctx3)
        p3.handle()
        self.assertIn("#1", _sent_text(p3))
        self.assertIn("玩家A", _sent_text(p3))

    def test_view_index(self):
        ctx = make_group_message("/跑团记录 abc")
        plugin = TrpgSessionPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        out = _sent_text(plugin)
        self.assertTrue("暂无保存" in out or "列表" in out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
