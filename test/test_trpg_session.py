"""测试 TRPG 会话录制插件与录制落盘（AC01–AC04、AC10）。

运行: pytest test/test_trpg_session.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import character_store as store
from core.config import BOT_QQ, NICKNAME, WEB_BASE_URL
from core.trpg import records
from plugins.trpg_dice import TrpgPlugin
from plugins.trpg_session import TrpgSessionPlugin
from test.helper import MockApiWrapper, make_private_message
import core.context as runtime_context

GROUP_ID = 296470819
BOT_ID = str(BOT_QQ)


# ── 桩与工具 ──────────────────────────────────────────

class RecordingApi(MockApiWrapper):
    """补上录制依赖的图片地址解析（MockApiWrapper 一律返回空）。"""

    def __init__(self, ctx, image_url=""):
        super().__init__(ctx)
        self.image_url = image_url

    def get_image_url(self, file):
        return self.image_url


def _text_seg(text: str) -> dict:
    return {"type": "text", "data": {"text": text}}


def _group_event(segments, user_id=111, nickname="玩家A", group_id=GROUP_ID, ts=0) -> dict:
    return {
        "post_type": "message",
        "message_type": "group",
        "user_id": user_id,
        "group_id": group_id,
        "message": segments,
        "sender": {"user_id": user_id, "nickname": nickname, "role": "member"},
        "time": ts,
        "message_id": -1,
    }


def _run(segments, api_cls=MockApiWrapper, api_kwargs=None, **kwargs) -> TrpgSessionPlugin:
    ctx = _group_event(segments, **kwargs)
    plugin = TrpgSessionPlugin(ctx)
    plugin.api = api_cls(ctx, **(api_kwargs or {}))
    plugin.handle()
    return plugin


def _sent_text(plugin) -> str:
    assert len(plugin.api.sent_messages) >= 1
    return plugin.api.sent_messages[-1][1][0]["data"]["text"]


def _fake_download(url, local_path, expected_size=None):
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    Path(local_path).write_bytes(b"fake-image")
    return True, ""


class IsolationMixin:
    """清空运行时录制状态；需要落盘时用临时数据目录，绝不写真实 server_data。"""

    def setUp(self):
        self._reset_state()

    def tearDown(self):
        self._reset_state()

    def _reset_state(self):
        runtime_context.recording_sessions.clear()
        runtime_context.last_completed.clear()
        runtime_context.group_roles.clear()
        # 群名走 HTTP，本机无 OneBot 时每次尝试要等 2 秒连接失败；默认桩掉，个别用例自行覆盖
        self._group_name_patch = patch("plugins.trpg_session.resolve_group_name", return_value="")
        self._group_name_patch.start()
        self.addCleanup(self._group_name_patch.stop)

    def use_temp_data_path(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = patch("core.config.PYTHON_DATA_PATH", tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.root = Path(tmp.name) / "trpg_records"
        return self.root

    def record_dir(self, group_id=GROUP_ID) -> Path:
        """该群唯一记录目录（录制目录名由开始时间决定）。"""
        dirs = sorted(p for p in (self.root / str(group_id)).iterdir() if p.is_dir())
        assert len(dirs) == 1, f"期望 1 个记录目录，实际 {dirs}"
        return dirs[0]

    def messages(self, path: Path) -> list[dict]:
        entries, skipped = records.iter_messages(path)
        assert skipped == 0, f"messages.jsonl 出现 {skipped} 行坏数据"
        return entries

    def meta(self, path: Path) -> dict:
        return json.loads((path / "meta.json").read_text(encoding="utf-8"))


# ── 指令匹配 ──────────────────────────────────────────

class TestTrpgSessionMatch(IsolationMixin, unittest.TestCase):
    def test_match_command(self):
        ctx = _group_event([_text_seg("/跑团记录 开始")])
        self.assertTrue(TrpgSessionPlugin(ctx).match("message"))

    def test_match_list(self):
        ctx = _group_event([_text_seg("/跑团记录 列表")])
        self.assertTrue(TrpgSessionPlugin(ctx).match("message"))

    def test_match_plain_command(self):
        ctx = _group_event([_text_seg("/跑团记录")])
        self.assertTrue(TrpgSessionPlugin(ctx).match("message"))

    def test_no_match_other(self):
        ctx = _group_event([_text_seg(".r 2d6")])
        self.assertFalse(TrpgSessionPlugin(ctx).match("message"))

    def test_no_match_non_message(self):
        ctx = _group_event([_text_seg("hello")])
        self.assertFalse(TrpgSessionPlugin(ctx).match("notice"))

    def test_match_all_during_recording(self):
        runtime_context.recording_sessions[GROUP_ID] = {"start": None, "messages": [], "participants": {}}
        ctx = _group_event([_text_seg("普通聊天消息")])
        self.assertTrue(TrpgSessionPlugin(ctx).match("message"))

    def test_private_message_refused(self):
        ctx = make_private_message("/跑团记录 开始")
        plugin = TrpgSessionPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        self.assertIn("只能在群聊中使用", _sent_text(plugin))


# ── AC01 录制落盘 ──────────────────────────────────────

class TestRecordFilesOnDisk(IsolationMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.use_temp_data_path()

    def test_start_creates_dir_and_meta(self):
        _run([_text_seg("/跑团记录 开始")])
        self.assertTrue(runtime_context.is_group_recording(GROUP_ID))
        path = self.record_dir()
        self.assertTrue(path.is_dir())
        self.assertTrue((path / "imgs").is_dir())
        meta = self.meta(path)
        self.assertEqual(meta["version"], 2)
        self.assertEqual(meta["group_id"], GROUP_ID)
        self.assertEqual(meta["group_name"], "")
        self.assertTrue(meta["start"])
        self.assertIsNone(meta["end"])
        self.assertEqual(meta["participants"], [])
        self.assertEqual(meta["roles"], {})

    def test_messages_jsonl_appends_one_line_per_message(self):
        _run([_text_seg("/跑团记录 开始")])
        _run([_text_seg("我推开酒馆的门")], user_id=111, nickname="玩家A")
        _run([_text_seg("第二句")], user_id=111, nickname="玩家A")
        path = self.record_dir()
        self.assertTrue((path / "messages.jsonl").is_file())
        entries = self.messages(path)
        self.assertEqual(len(entries), 2)
        first = entries[0]
        for key in records.MESSAGE_KEYS:
            self.assertIn(key, first)
        self.assertEqual(first["sender_type"], "user")
        self.assertEqual(first["user_id"], "111")
        self.assertEqual(first["nickname"], "玩家A")
        self.assertEqual(first["char_name"], "")
        self.assertEqual(first["role"], "")
        self.assertEqual(first["segments"], [{"type": "text", "text": "我推开酒馆的门"}])
        self.assertIsInstance(first["time"], int)
        self.assertEqual(entries[1]["segments"], [{"type": "text", "text": "第二句"}])

    def test_participants_synced_on_first_speech(self):
        _run([_text_seg("/跑团记录 开始")])
        _run([_text_seg("我推开酒馆的门")], user_id=111, nickname="玩家A")
        participants = self.meta(self.record_dir())["participants"]
        self.assertEqual(len(participants), 1)
        self.assertEqual(participants[0]["user_id"], "111")
        self.assertEqual(participants[0]["nickname"], "玩家A")
        self.assertEqual(participants[0]["char_name"], "")

    def test_participant_char_name_recorded(self):
        chars_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(chars_tmp.cleanup)
        chars_patch = patch("core.character_store.CHARS_ROOT", Path(chars_tmp.name))
        chars_patch.start()
        self.addCleanup(chars_patch.stop)
        store.create_char("111", {"char_name": "艾拉"})

        _run([_text_seg("/跑团记录 开始")])
        _run([_text_seg("我推开酒馆的门")], user_id=111, nickname="玩家A")
        path = self.record_dir()
        self.assertEqual(self.messages(path)[0]["char_name"], "艾拉")
        self.assertEqual(self.meta(path)["participants"][0]["char_name"], "艾拉")

    def test_recording_skips_bot_own_message(self):
        _run([_text_seg("/跑团记录 开始")])
        # 机器人自己发出的群消息由 record_bot_message 入档，不再经 message 事件重复录制
        _run([_text_seg("bot 消息")], user_id=int(BOT_QQ), nickname="小埃同学")
        self.assertEqual(self.messages(self.record_dir()), [])

    def test_at_segment_recorded(self):
        _run([_text_seg("/跑团记录 开始")])
        _run([{"type": "at", "data": {"qq": "123456"}}, _text_seg("你看这里")], user_id=111)
        self.assertEqual(
            self.messages(self.record_dir())[0]["segments"],
            [{"type": "at", "qq": "123456"}, {"type": "text", "text": "你看这里"}],
        )


# ── AC02 图片入档 ──────────────────────────────────────

class TestImageRecording(IsolationMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.use_temp_data_path()
        _run([_text_seg("/跑团记录 开始")])

    @patch("plugins.trpg_session.download_image", side_effect=_fake_download)
    def test_image_saved_to_imgs(self, _mock_dl):
        _run(
            [{"type": "image", "data": {"file": "a.jpg"}}],
            api_cls=RecordingApi,
            api_kwargs={"image_url": "https://example.test/a.jpg"},
        )
        path = self.record_dir()
        self.assertTrue((path / "imgs" / "img_0001.jpg").is_file())
        self.assertEqual(
            self.messages(path)[0]["segments"],
            [{"type": "image", "local": "imgs/img_0001.jpg"}],
        )

    @patch("plugins.trpg_session.download_image", return_value=(False, "HTTP状态码异常"))
    def test_download_failure_marks_segment_unavailable(self, _mock_dl):
        _run(
            [{"type": "image", "data": {"file": "a.jpg"}}],
            api_cls=RecordingApi,
            api_kwargs={"image_url": "https://example.test/a.jpg"},
        )
        _run([_text_seg("后续消息照常入档")], user_id=111)
        entries = self.messages(self.record_dir())
        self.assertEqual(len(entries), 2)
        self.assertEqual(
            entries[0]["segments"],
            [{"type": "image", "unavailable": True, "file": "a.jpg"}],
        )
        self.assertEqual(entries[1]["segments"], [{"type": "text", "text": "后续消息照常入档"}])

    def test_image_url_failure_marks_segment_unavailable(self):
        # get_image_url 返回空串（OneBot 失败）走同一条降级路径
        _run([{"type": "image", "data": {"file": "a.jpg"}}], api_cls=RecordingApi)
        self.assertEqual(
            self.messages(self.record_dir())[0]["segments"][0]["unavailable"],
            True,
        )


# ── AC03/AC10 机器人消息、群名与暗骰标记 ─────────────────

class TestBotMessageRecording(IsolationMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.use_temp_data_path()
        _run([_text_seg("/跑团记录 开始")])

    def _run_dice(self, text: str, user_id=111, nickname="玩家A") -> TrpgPlugin:
        ctx = _group_event([_text_seg(text)], user_id=user_id, nickname=nickname)
        plugin = TrpgPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        return plugin

    def test_dice_result_recorded_as_bot(self):
        self._run_dice(".r 1d6")
        entries = self.messages(self.record_dir())
        bots = [e for e in entries if e["sender_type"] == "bot"]
        self.assertEqual(len(bots), 1)
        self.assertEqual(bots[0]["user_id"], BOT_ID)
        self.assertEqual(bots[0]["nickname"], NICKNAME)
        self.assertIn("玩家A", bots[0]["segments"][0]["text"])
        self.assertNotIn("secret", bots[0])
        self.assertEqual(
            [p["user_id"] for p in self.meta(self.record_dir())["participants"]],
            [BOT_ID],
        )

    def test_dark_roll_recorded_as_secret(self):
        # 暗骰结果只在私聊出现；群里只有「悄悄掷出骰子」提示
        plugin = self._run_dice(".rh d20")
        group_texts = [m[1][0]["data"]["text"] for m in plugin.api.sent_messages if m[0] == "send_msg"]
        private_texts = [m[1][0]["data"]["text"] for m in plugin.api.sent_messages if m[0] == "send_private_msg"]
        self.assertEqual(group_texts, ["悄悄掷出骰子"])
        self.assertEqual(len(private_texts), 1)

        entries = self.messages(self.record_dir())
        hints = [e for e in entries if e["sender_type"] == "bot" and not e.get("secret")]
        secrets = [e for e in entries if e.get("secret")]
        self.assertEqual([e["segments"][0]["text"] for e in hints], ["悄悄掷出骰子"])
        self.assertEqual(len(secrets), 1)
        self.assertEqual(secrets[0]["sender_type"], "bot")
        self.assertEqual(secrets[0]["user_id"], BOT_ID)
        self.assertEqual(secrets[0]["segments"][0]["text"], private_texts[0])

    def test_role_notice_recorded_as_bot(self):
        _run([_text_seg(".dm")], user_id=111, nickname="玩家A")
        bots = [e for e in self.messages(self.record_dir()) if e["sender_type"] == "bot"]
        self.assertEqual(len(bots), 1)
        self.assertIn("已将 玩家A 设为DM", bots[0]["segments"][0]["text"])
        self.assertEqual(self.meta(self.record_dir())["roles"], {"111": "dm"})

    def test_dark_roll_private_chat_not_recorded(self):
        # 私聊暗骰没有群号，不入档也不报错
        ctx = make_private_message(".rh d20")
        plugin = TrpgPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        self.assertEqual(self.messages(self.record_dir()), [])


class TestGroupName(IsolationMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.use_temp_data_path()

    def test_group_name_written_when_available(self):
        with patch("plugins.trpg_session.resolve_group_name", return_value="夜航团"):
            _run([_text_seg("/跑团记录 开始")], api_cls=RecordingApi)
        self.assertEqual(self.meta(self.record_dir())["group_name"], "夜航团")

    def test_group_name_failure_keeps_recording(self):
        with patch("plugins.trpg_session.resolve_group_name", return_value=""):
            plugin = _run([_text_seg("/跑团记录 开始")], api_cls=RecordingApi)
        self.assertIn("已开始", _sent_text(plugin))
        self.assertEqual(self.meta(self.record_dir())["group_name"], "")
        self.assertTrue(runtime_context.is_group_recording(GROUP_ID))


# ── 开始/结束的既有守卫 ────────────────────────────────

class TestStartGuards(IsolationMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.use_temp_data_path()

    def test_start_twice_warns(self):
        _run([_text_seg("/跑团记录 开始")])
        plugin = _run([_text_seg("/跑团记录 开始")])
        self.assertIn("已在录制", _sent_text(plugin))
        self.assertEqual(len(list((self.root / str(GROUP_ID)).iterdir())), 1)

    def test_start_with_unexported_warns(self):
        runtime_context.last_completed[GROUP_ID] = {"messages": [{"dummy": True}]}
        plugin = _run([_text_seg("/跑团记录 开始")])
        self.assertIn("尚未导出", _sent_text(plugin))
        self.assertFalse(runtime_context.is_group_recording(GROUP_ID))

    def test_force_start_discards_unexported(self):
        runtime_context.last_completed[GROUP_ID] = {"messages": [{"dummy": True}]}
        plugin = _run([_text_seg("/跑团记录 强制开始")])
        self.assertIn("已丢弃", _sent_text(plugin))
        self.assertTrue(runtime_context.is_group_recording(GROUP_ID))
        self.assertIsNone(runtime_context.get_last_completed(GROUP_ID))

    def test_stop_while_not_recording(self):
        plugin = _run([_text_seg("/跑团记录 结束")])
        self.assertIn("没有进行中", _sent_text(plugin))

    def test_export_while_recording_refused(self):
        _run([_text_seg("/跑团记录 开始")])
        plugin = _run([_text_seg("/跑团记录 导出")])
        self.assertIn("录制中无法导出", _sent_text(plugin))

    def test_export_no_completed_refused(self):
        plugin = _run([_text_seg("/跑团记录 导出")])
        self.assertIn("没有可导出", _sent_text(plugin))


# ── AC04 结束与导出 ────────────────────────────────────

class TestStopAndExport(IsolationMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.use_temp_data_path()
        _run([_text_seg("/跑团记录 开始")])
        _run([_text_seg("我推开酒馆的门")], user_id=111, nickname="玩家A")
        _run([_text_seg("/跑团记录 结束")])

    def test_stop_writes_end(self):
        path = self.record_dir()
        self.assertTrue(self.meta(path)["end"])
        self.assertFalse((path / "record.md").is_file())
        self.assertFalse(runtime_context.is_group_recording(GROUP_ID))

    def test_export_report_contains_web_link(self):
        plugin = _run([_text_seg("/跑团记录 导出")])
        path = self.record_dir()
        self.assertIn("导出成功", _sent_text(plugin))
        self.assertIn(
            f"查看：{WEB_BASE_URL}/trpg/records/{GROUP_ID}/{path.name}",
            _sent_text(plugin),
        )
        self.assertTrue((path / "record.md").is_file())

    def test_export_md_generated_from_jsonl(self):
        plugin = _run([_text_seg("/跑团记录 导出")])
        path = self.record_dir()
        md = (path / "record.md").read_text(encoding="utf-8")
        meta = self.meta(path)
        entries = self.messages(path)
        self.assertIn(f"- 开始时间：{meta['start']}", md)
        self.assertIn(f"- 结束时间：{meta['end']}", md)
        self.assertIn("玩家A", md)
        self.assertIn("我推开酒馆的门", md)
        # 每条消息的发送方与正文都来自 messages.jsonl
        for entry in entries:
            self.assertIn(entry["segments"][0]["text"], md)
        self.assertIn("导出成功", _sent_text(plugin))


class TestExportRichSegments(IsolationMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.use_temp_data_path()
        _run([_text_seg("/跑团记录 开始")])
        _run([_text_seg(".dm")], user_id=111, nickname="玩家A")

    @patch("plugins.trpg_session.download_image", side_effect=_fake_download)
    def test_md_keeps_role_prefix_image_and_mention(self, _mock_dl):
        _run(
            [_text_seg("看一下这个"), {"type": "image", "data": {"file": "a.jpg"}},
             {"type": "at", "data": {"qq": "123456"}}],
            api_cls=RecordingApi,
            api_kwargs={"image_url": "https://example.test/a.jpg"},
            user_id=111,
            nickname="玩家A",
        )
        _run([_text_seg("/跑团记录 结束")])
        _run([_text_seg("/跑团记录 导出")])
        md = (self.record_dir() / "record.md").read_text(encoding="utf-8")
        self.assertIn("[DM] 玩家A", md)
        self.assertIn("看一下这个", md)
        self.assertIn("![图片](imgs/img_0001.jpg)", md)
        self.assertIn("@123456", md)


# ── 列表与查看 ────────────────────────────────────────

class TestListAndView(IsolationMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.use_temp_data_path()
        _run([_text_seg("/跑团记录 开始")])
        _run([_text_seg("我推开酒馆的门")], user_id=111, nickname="玩家A")
        _run([_text_seg("/跑团记录 结束")])

    def test_list_shows_state_and_count(self):
        plugin = _run([_text_seg("/跑团记录 列表")])
        out = _sent_text(plugin)
        self.assertIn("[1]", out)
        self.assertIn("已结束·未导出", out)
        self.assertIn("1 条", out)

    def test_view_shows_participants(self):
        plugin = _run([_text_seg("/跑团记录 #1")])
        out = _sent_text(plugin)
        self.assertIn("#1", out)
        self.assertIn("玩家A", out)
        self.assertIn("已结束·未导出", out)

    def test_view_index_out_of_range(self):
        plugin = _run([_text_seg("/跑团记录 #9")])
        self.assertIn("编号无效", _sent_text(plugin))


class TestListEmpty(IsolationMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.use_temp_data_path()

    def test_list_empty(self):
        plugin = _run([_text_seg("/跑团记录 列表")])
        self.assertIn("暂无", _sent_text(plugin))

    def test_view_without_records(self):
        plugin = _run([_text_seg("/跑团记录 #1")])
        self.assertIn("暂无", _sent_text(plugin))


if __name__ == "__main__":
    unittest.main(verbosity=2)
