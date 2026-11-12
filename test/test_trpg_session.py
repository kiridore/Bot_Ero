"""测试 TRPG 会话录制插件与录制落盘（AC01–AC04、AC10）。

运行: pytest test/test_trpg_session.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import character_store as store
from core.config import BOT_QQ, NICKNAME, WEB_BASE_URL
from core.trpg import party, records
from plugins.trpg_dice import TrpgPlugin
from plugins.trpg_session import TrpgSessionPlugin, recover_recordings
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
        # 群名与成员名单都走 HTTP，本机无 OneBot 时每次尝试要等 2 秒连接失败；默认桩掉，个别用例自行覆盖
        self._group_name_patch = patch("plugins.trpg_session.resolve_group_name", return_value="")
        self._group_name_patch.start()
        self.addCleanup(self._group_name_patch.stop)
        self.patch_members([])

    def patch_members(self, members):
        patcher = patch("plugins.trpg_session.fetch_group_members", return_value=members)
        patcher.start()
        self.addCleanup(patcher.stop)

    def seed_party(self, dm_id="111", members=None, prepared=None):
        """把 dm_id 设为 DM，可选预置准备名单与成员列表。"""
        party.set_role(GROUP_ID, dm_id, "dm")
        for uid, snap in (prepared or {}).items():
            party.set_prepared(GROUP_ID, uid, {"user_id": str(uid), **snap})
        self.patch_members(members if members is not None else [
            {"user_id": str(dm_id), "nickname": "玩家A", "is_robot": False}
        ])

    def use_temp_data_path(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = patch("core.config.PYTHON_DATA_PATH", tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        # 角色卡根目录是另一份配置，不隔离会让先跑的用例把车牌漏给后跑的用例
        chars_patch = patch("core.character_store.CHARS_ROOT", Path(tmp.name) / "trpg_chars")
        chars_patch.start()
        self.addCleanup(chars_patch.stop)
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
        ctx = _group_event([_text_seg("/跑团 记录 开始")])
        self.assertTrue(TrpgSessionPlugin(ctx).match("message"))

    def test_match_list(self):
        ctx = _group_event([_text_seg("/跑团 记录 列表")])
        self.assertTrue(TrpgSessionPlugin(ctx).match("message"))

    def test_match_plain_command(self):
        ctx = _group_event([_text_seg("/跑团 记录")])
        self.assertTrue(TrpgSessionPlugin(ctx).match("message"))

    def test_no_match_other(self):
        ctx = _group_event([_text_seg(".r 2d6")])
        self.assertFalse(TrpgSessionPlugin(ctx).match("message"))

    def test_old_command_not_matched(self):
        ctx = _group_event([_text_seg("/跑团记录 开始")])
        self.assertFalse(TrpgSessionPlugin(ctx).match("message"))

    def test_role_subcommand_left_to_char_plugin(self):
        ctx = _group_event([_text_seg("/跑团 角色 查看")])
        self.assertFalse(TrpgSessionPlugin(ctx).match("message"))

    def test_no_match_non_message(self):
        ctx = _group_event([_text_seg("hello")])
        self.assertFalse(TrpgSessionPlugin(ctx).match("notice"))

    def test_match_all_during_recording(self):
        runtime_context.recording_sessions[GROUP_ID] = {"start": None, "messages": [], "participants": {}}
        ctx = _group_event([_text_seg("普通聊天消息")])
        self.assertTrue(TrpgSessionPlugin(ctx).match("message"))

    def test_private_message_refused(self):
        ctx = make_private_message("/跑团 记录 开始")
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
        _run([_text_seg("/跑团 记录 强制开始")])
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
        _run([_text_seg("/跑团 记录 强制开始")])
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
        _run([_text_seg("/跑团 记录 强制开始")])
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

        _run([_text_seg("/跑团 记录 强制开始")])
        _run([_text_seg("我推开酒馆的门")], user_id=111, nickname="玩家A")
        path = self.record_dir()
        self.assertEqual(self.messages(path)[0]["char_name"], "艾拉")
        self.assertEqual(self.meta(path)["participants"][0]["char_name"], "艾拉")

    def test_recording_skips_bot_own_message(self):
        _run([_text_seg("/跑团 记录 强制开始")])
        # 机器人自己发出的群消息由 record_bot_message 入档，不再经 message 事件重复录制
        _run([_text_seg("bot 消息")], user_id=int(BOT_QQ), nickname="小埃同学")
        self.assertEqual(self.messages(self.record_dir()), [])

    def test_at_segment_recorded(self):
        _run([_text_seg("/跑团 记录 强制开始")])
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
        _run([_text_seg("/跑团 记录 强制开始")])

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
        _run([_text_seg("/跑团 记录 强制开始")])

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
            _run([_text_seg("/跑团 记录 强制开始")], api_cls=RecordingApi)
        self.assertEqual(self.meta(self.record_dir())["group_name"], "夜航团")

    def test_group_name_failure_keeps_recording(self):
        with patch("plugins.trpg_session.resolve_group_name", return_value=""):
            plugin = _run([_text_seg("/跑团 记录 强制开始")], api_cls=RecordingApi)
        self.assertIn("已开始", _sent_text(plugin))
        self.assertEqual(self.meta(self.record_dir())["group_name"], "")
        self.assertTrue(runtime_context.is_group_recording(GROUP_ID))


# ── 开始/结束守卫与结束归档 ────────────────────────────

class TestStartGuards(IsolationMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.use_temp_data_path()

    def test_start_twice_warns(self):
        _run([_text_seg("/跑团 记录 强制开始")])
        plugin = _run([_text_seg("/跑团 记录 强制开始")])
        self.assertIn("已在录制", _sent_text(plugin))
        self.assertEqual(len(list((self.root / str(GROUP_ID)).iterdir())), 1)

    def test_stop_while_not_recording(self):
        plugin = _run([_text_seg("/跑团 记录 结束")])
        self.assertIn("没有进行中", _sent_text(plugin))

    def test_stop_requires_dm(self):
        _run([_text_seg("/跑团 记录 强制开始")])
        plugin = _run([_text_seg("/跑团 记录 结束")])
        self.assertIn("只有 DM", _sent_text(plugin))
        self.assertTrue(runtime_context.is_group_recording(GROUP_ID))

    def test_export_command_removed(self):
        plugin = _run([_text_seg("/跑团 记录 导出")])
        self.assertIn("暂无", _sent_text(plugin))


class TestStopArchive(IsolationMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.use_temp_data_path()
        self.seed_party()
        _run([_text_seg("/跑团 记录 开始")])
        _run([_text_seg("我推开酒馆的门")], user_id=111, nickname="玩家A")
        self.stop_plugin = _run([_text_seg("/跑团 记录 结束")])

    def test_stop_writes_end_and_md(self):
        path = self.record_dir()
        self.assertTrue(self.meta(path)["end"])
        self.assertTrue((path / "record.md").is_file())
        self.assertFalse(runtime_context.is_group_recording(GROUP_ID))

    def test_stop_reply_contains_web_link(self):
        path = self.record_dir()
        self.assertIn(
            f"查看：{WEB_BASE_URL}/trpg/records/{GROUP_ID}/{path.name}",
            _sent_text(self.stop_plugin),
        )

    def test_md_generated_from_jsonl(self):
        path = self.record_dir()
        md = (path / "record.md").read_text(encoding="utf-8")
        meta = self.meta(path)
        self.assertIn(f"- 开始时间：{meta['start']}", md)
        self.assertIn(f"- 结束时间：{meta['end']}", md)
        self.assertIn("[DM] 玩家A", md)
        self.assertIn("我推开酒馆的门", md)


class TestArchiveRichSegments(IsolationMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.use_temp_data_path()
        self.seed_party()
        _run([_text_seg("/跑团 记录 开始")])

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
        _run([_text_seg("/跑团 记录 结束")])
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
        self.seed_party()
        _run([_text_seg("/跑团 记录 开始")])
        _run([_text_seg("我推开酒馆的门")], user_id=111, nickname="玩家A")
        _run([_text_seg("/跑团 记录 结束")])

    def test_list_shows_state_and_count(self):
        plugin = _run([_text_seg("/跑团 记录 列表")])
        out = _sent_text(plugin)
        self.assertIn("[1]", out)
        self.assertIn("已结束", out)
        self.assertIn("1 条", out)

    def test_view_shows_participants(self):
        plugin = _run([_text_seg("/跑团 记录 #1")])
        out = _sent_text(plugin)
        self.assertIn("#1", out)
        self.assertIn("玩家A", out)
        self.assertIn("已结束", out)

    def test_view_index_out_of_range(self):
        plugin = _run([_text_seg("/跑团 记录 #9")])
        self.assertIn("编号无效", _sent_text(plugin))


class TestListEmpty(IsolationMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.use_temp_data_path()

    def test_list_empty(self):
        plugin = _run([_text_seg("/跑团 记录 列表")])
        self.assertIn("暂无", _sent_text(plugin))

    def test_view_without_records(self):
        plugin = _run([_text_seg("/跑团 记录 #1")])
        self.assertIn("暂无", _sent_text(plugin))



# ── AC01–AC03 准备与卡片 ────────────────────────────

def _joined(plugin) -> str:
    """把最后一条消息的分段拼成可断言文本（@ 显示为 @QQ）。"""
    segs = plugin.api.sent_messages[-1][1]
    return "".join(
        seg["data"].get("text", "") if seg.get("type") == "text" else "@" + str(seg["data"].get("qq"))
        for seg in segs
    )


class TestPartyCard(IsolationMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.use_temp_data_path()

    def test_card_lists_dm_and_pending(self):
        self.patch_members([
            {"user_id": "111", "nickname": "老张", "is_robot": False},
            {"user_id": "222", "nickname": "小王", "is_robot": False},
        ])
        _run([_text_seg(".dm")], user_id=111, nickname="老张")
        out = _joined(_run([_text_seg("/跑团")]))
        self.assertIn("DM：老张", out)
        self.assertIn("已准备 0/1", out)
        self.assertIn("@222", out)

    def test_dm_unique(self):
        self.patch_members([
            {"user_id": "111", "nickname": "老张", "is_robot": False},
            {"user_id": "222", "nickname": "小王", "is_robot": False},
        ])
        _run([_text_seg(".dm")], user_id=111, nickname="老张")
        _run([_text_seg(".dm")], user_id=222, nickname="小王")
        self.assertEqual(party.read_pending(GROUP_ID)["roles"], {"222": "dm"})

    def test_ob_replaces_dm_for_same_user(self):
        self.patch_members([{"user_id": "111", "nickname": "老张", "is_robot": False}])
        _run([_text_seg(".dm")], user_id=111, nickname="老张")
        _run([_text_seg(".ob")], user_id=111, nickname="老张")
        self.assertEqual(party.read_pending(GROUP_ID)["roles"], {"111": "ob"})

    def test_card_notes_unavailable_members(self):
        self.patch_members(None)
        out = _joined(_run([_text_seg("/跑团")]))
        self.assertIn("成员名单不可用", out)


class TestPrepare(IsolationMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.use_temp_data_path()
        self.patch_members([{"user_id": "111", "nickname": "玩家A", "is_robot": False}])

    def test_prepare_without_char_refused(self):
        plugin = _run([_text_seg("/跑团 准备")])
        self.assertIn("角色卡", _sent_text(plugin))
        self.assertEqual(party.read_pending(GROUP_ID)["prepared"], {})

    def test_prepare_records_snapshot(self):
        store.create_char("111", {"char_name": "艾拉", "race": "精灵", "class_name": "游侠", "level": 3})
        out = _joined(_run([_text_seg("/跑团 准备")]))
        prepared = party.read_pending(GROUP_ID)["prepared"]["111"]
        self.assertEqual(prepared["char_name"], "艾拉")
        self.assertEqual(prepared["level"], 3)
        self.assertIn("艾拉", out)

    def test_snapshot_survives_char_switch(self):
        first = store.create_char("111", {"char_name": "艾拉", "race": "精灵", "class_name": "游侠", "level": 3})
        second = store.create_char("111", {"char_name": "阿铁", "race": "人类", "class_name": "战士", "level": 2})
        _run([_text_seg("/跑团 准备")])
        store.set_current("111", second)
        self.assertEqual(party.read_pending(GROUP_ID)["prepared"]["111"]["char_name"], "艾拉")
        self.assertNotEqual(first, second)

    def test_unprepare_removes_entry(self):
        store.create_char("111", {"char_name": "艾拉", "race": "精灵", "class_name": "游侠", "level": 3})
        _run([_text_seg("/跑团 准备")])
        _run([_text_seg("/跑团 取消准备")])
        self.assertEqual(party.read_pending(GROUP_ID)["prepared"], {})

    def test_prepare_refused_during_recording(self):
        _run([_text_seg("/跑团 记录 强制开始")])
        plugin = _run([_text_seg("/跑团 准备")])
        self.assertIn("录制中无法准备", _sent_text(plugin))


# ── AC04–AC06 准入校验与开录预置 ────────────────────

def _member(uid, nickname, is_robot=False):
    return {"user_id": str(uid), "nickname": nickname, "is_robot": is_robot}


class TestGate(IsolationMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.use_temp_data_path()

    def _start(self, force=False):
        return _run([_text_seg("/跑团 记录 强制开始" if force else "/跑团 记录 开始")])

    def test_no_dm_refused(self):
        self.patch_members([_member(111, "玩家A")])
        store.create_char("111", {"char_name": "艾拉"})
        plugin = self._start()
        self.assertIn("DM", _joined(plugin))
        self.assertFalse(runtime_context.is_group_recording(GROUP_ID))

    def test_missing_char_and_prepare_reported_together(self):
        self.seed_party(dm_id="111", members=[_member(111, "DM"), _member(222, "无卡"), _member(333, "未准备")])
        store.create_char("333", {"char_name": "阿铁"})
        out = _joined(self._start())
        self.assertIn("缺少角色卡", out)
        self.assertIn("@222", out)
        self.assertIn("尚未准备", out)
        self.assertIn("@333", out)
        self.assertFalse(runtime_context.is_group_recording(GROUP_ID))

    def test_dm_and_ob_exempt_from_card_and_prepare(self):
        self.seed_party(dm_id="111", members=[_member(111, "DM"), _member(222, "OB"), _member(333, "玩家C")])
        party.set_role(GROUP_ID, "222", "ob")
        store.create_char("333", {"char_name": "阿铁", "race": "人类", "class_name": "战士", "level": 2})
        party.set_prepared(GROUP_ID, "333", {
            "user_id": "333", "nickname": "玩家C", "char_id": 1, "char_name": "阿铁",
            "race": "人类", "class_name": "战士", "level": 2, "prepared_at": "2026-11-10 20:00:00",
        })
        self._start()
        self.assertTrue(runtime_context.is_group_recording(GROUP_ID))

    def test_members_unavailable_refused(self):
        self.seed_party(dm_id="111")
        self.patch_members(None)
        out = _joined(self._start())
        self.assertIn("无法获取群成员列表", out)
        self.assertFalse(runtime_context.is_group_recording(GROUP_ID))

    def test_member_limit_refused(self):
        self.seed_party(dm_id="111")
        self.patch_members([_member(111, "DM")] + [_member(200000 + i, f"成员{i}") for i in range(201)])
        out = _joined(self._start())
        self.assertIn("超过校验上限", out)
        self.assertFalse(runtime_context.is_group_recording(GROUP_ID))

    def test_bot_member_excluded(self):
        self.seed_party(dm_id="111", members=[_member(111, "DM"), _member(BOT_QQ, "小埃", True)])
        self._start()
        self.assertTrue(runtime_context.is_group_recording(GROUP_ID))

    def test_force_start_bypasses_gate(self):
        self.patch_members([_member(222, "无卡")])
        plugin = self._start(force=True)
        self.assertIn("已开始", _sent_text(plugin))
        self.assertTrue(runtime_context.is_group_recording(GROUP_ID))


class TestStartSeed(IsolationMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.use_temp_data_path()

    def test_participants_preseeded_and_pending_cleared(self):
        self.seed_party(dm_id="111", members=[_member(111, "DM"), _member(222, "玩家B")])
        store.create_char("222", {"char_name": "阿铁", "race": "人类", "class_name": "战士", "level": 2})
        party.set_prepared(GROUP_ID, "222", {
            "user_id": "222", "nickname": "玩家B", "char_id": 1, "char_name": "阿铁",
            "race": "人类", "class_name": "战士", "level": 2, "prepared_at": "2026-11-10 20:00:00",
        })
        _run([_text_seg("/跑团 记录 开始")])
        meta = self.meta(self.record_dir())
        self.assertEqual([p["user_id"] for p in meta["participants"]], ["111", "222"])
        self.assertEqual(meta["roles"], {"111": "dm"})
        self.assertEqual(meta["participants"][1]["char_name"], "阿铁")
        self.assertFalse(party.pending_path(GROUP_ID).exists())

    def test_dm_nickname_saved_in_pending(self):
        """DM/观察者不准备、没有快照，昵称要单独存下来供网页名单显示。"""
        self.patch_members([_member(111, "老张"), _member(222, "小王")])
        _run([_text_seg(".dm")], user_id=111, nickname="老张")
        data = party.read_pending(GROUP_ID)
        self.assertEqual(data["roles"], {"111": "dm"})
        self.assertEqual(data.get("role_names"), {"111": "老张"})

        _run([_text_seg(".ob")], user_id=222, nickname="小王")
        data = party.read_pending(GROUP_ID)
        self.assertEqual(data.get("role_names"), {"111": "老张", "222": "小王"})

    def test_new_dm_replaces_old_nickname(self):
        self.patch_members([_member(111, "老张"), _member(222, "小王")])
        _run([_text_seg(".dm")], user_id=111, nickname="老张")
        _run([_text_seg(".dm")], user_id=222, nickname="小王")
        data = party.read_pending(GROUP_ID)
        self.assertEqual(data["roles"], {"222": "dm"})
        self.assertEqual(data.get("role_names"), {"222": "小王"})

    def test_card_excludes_bot_from_pending(self):
        """机器人自己与其它机器人不应出现在「未准备」列表里（也不计入分母）。"""
        from plugins.trpg_session import BOT_QQ
        self.seed_party(dm_id="111", members=[
            _member(111, "DM"), _member(222, "未准备"), _member(BOT_QQ, "小埃同学", is_robot=True),
            _member(999, "别的机器人", is_robot=True),
        ])
        _run([_text_seg(".dm")], user_id=111, nickname="DM")
        out = _joined(_run([_text_seg("/跑团")]))
        self.assertIn("开团准备", out)
        self.assertIn("已准备 0/1", out)
        self.assertIn("未准备", out)
        self.assertNotIn(str(BOT_QQ), out)
        self.assertNotIn("别的机器人", out)

    def test_pending_file_corrupt_is_tolerated(self):
        party.pending_path(GROUP_ID).parent.mkdir(parents=True, exist_ok=True)
        party.pending_path(GROUP_ID).write_text("not json", encoding="utf-8")
        out = _joined(_run([_text_seg("/跑团")]))
        self.assertIn("开团准备", out)


# ── AC01–AC05 重启恢复与心跳 ──────────────────────────

class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 11, 10, 20, 5, 0)


def _write_record(group_id, start_dir, *, end=None, start="2026-11-10 20:00:00", messages=(), imgs=()):
    path = records.group_dir(group_id) / start_dir
    (path / "imgs").mkdir(parents=True, exist_ok=True)
    records.rewrite_meta(path, {
        "version": 2,
        "group_id": group_id,
        "group_name": "夜航团",
        "start": start,
        "end": end,
        "roles": {"111": "dm"},
        "participants": [{"user_id": "111", "nickname": "玩家A", "char_name": "", "role": "dm"}],
    })
    for entry in messages:
        records.append_message(path, entry)
    for name in imgs:
        (path / "imgs" / name).write_bytes(b"x")
    return path


def _msg(ts, body="hello"):
    return {"time": ts, "sender_type": "user", "user_id": "111", "nickname": "玩家A",
            "char_name": "", "role": "", "segments": [{"type": "text", "text": body}]}


class TestRecovery(IsolationMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.use_temp_data_path()

    def test_resume_recent_record(self):
        now = int(time.time())
        path = _write_record(GROUP_ID, "2026-11-10_20-00-00", messages=[_msg(now - 3600)], imgs=["img_0003.jpg"])
        with patch("plugins.trpg_session.fetch_group_list", return_value={GROUP_ID}):
            self.assertEqual(recover_recordings(), 1)
        session = runtime_context.get_recording_session(GROUP_ID)
        self.assertEqual(session["dir"], path)
        self.assertEqual(session["img_count"], 3)
        self.assertTrue(session["resume_banner"])
        self.assertEqual(session["start"].strftime("%Y-%m-%d %H:%M:%S"), "2026-11-10 20:00:00")
        gap = self.messages(path)[-1]["segments"][0]["text"]
        self.assertIn("中断", gap)
        self.assertIn("恢复", gap)
        # 续录后新消息簿到同一目录
        _run([_text_seg("继续跑")], user_id=111, nickname="玩家A")
        self.assertEqual(len(self.messages(path)), 3)

    def test_resumed_image_number_continues(self):
        now = int(time.time())
        path = _write_record(GROUP_ID, "2026-11-10_20-00-00", messages=[_msg(now - 60)], imgs=["img_0003.jpg"])
        with patch("plugins.trpg_session.fetch_group_list", return_value={GROUP_ID}):
            recover_recordings()
        with patch("plugins.trpg_session.download_image", side_effect=_fake_download):
            _run([{"type": "image", "data": {"file": "b.jpg"}}],
                 api_cls=RecordingApi, api_kwargs={"image_url": "https://example.test/b.jpg"},
                 user_id=111, nickname="玩家A")
        self.assertTrue((path / "imgs" / "img_0004.jpg").is_file())

    def test_stale_record_finalized(self):
        old = int(time.time()) - 8 * 24 * 3600
        path = _write_record(GROUP_ID, "2026-10-01_20-00-00", messages=[_msg(old)])
        with patch("plugins.trpg_session.fetch_group_list", return_value={GROUP_ID}):
            self.assertEqual(recover_recordings(), 0)
        self.assertFalse(runtime_context.is_group_recording(GROUP_ID))
        self.assertEqual(self.meta(path)["end"], datetime.fromtimestamp(old).strftime("%Y-%m-%d %H:%M:%S"))
        self.assertTrue((path / "record.md").is_file())

    def test_dissolved_group_finalized(self):
        path = _write_record(GROUP_ID, "2026-11-09_20-00-00", messages=[_msg(int(time.time()) - 60)])
        with patch("plugins.trpg_session.fetch_group_list", return_value=set()):
            self.assertEqual(recover_recordings(), 0)
        self.assertTrue(self.meta(path)["end"])
        self.assertTrue((path / "record.md").is_file())

    def test_group_list_unavailable_still_resumes(self):
        _write_record(GROUP_ID, "2026-11-10_20-00-00", messages=[_msg(int(time.time()) - 60)])
        with patch("plugins.trpg_session.fetch_group_list", return_value=None):
            self.assertEqual(recover_recordings(), 1)

    def test_only_latest_resumed_for_same_group(self):
        now = int(time.time())
        older = _write_record(GROUP_ID, "2026-11-09_20-00-00", start="2026-11-09 20:00:00", messages=[_msg(now - 7200)])
        newer = _write_record(GROUP_ID, "2026-11-10_20-00-00", start="2026-11-10 20:00:00", messages=[_msg(now - 60)])
        with patch("plugins.trpg_session.fetch_group_list", return_value={GROUP_ID}):
            self.assertEqual(recover_recordings(), 1)
        self.assertEqual(runtime_context.get_recording_session(GROUP_ID)["dir"], newer)
        self.assertTrue(self.meta(older)["end"])


class TestHeartbeat(IsolationMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.use_temp_data_path()

    def _plugin(self):
        ctx = {"post_type": "meta", "meta_event_type": "heartbeat"}
        plugin = TrpgSessionPlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        return plugin

    def test_heartbeat_runs_every_five_minutes(self):
        plugin = self._plugin()
        with patch("plugins.trpg_session.datetime", _FixedDateTime):
            self.assertTrue(plugin.should_run_on_heartbeat("meta"))
            self.assertFalse(plugin.should_run_on_heartbeat("meta"))
        self.assertFalse(plugin.should_run_on_heartbeat("message"))

    def test_heartbeat_skips_poll_without_recordings(self):
        plugin = self._plugin()
        with patch("plugins.trpg_session.fetch_group_list") as fake:
            plugin._on_heartbeat()
        fake.assert_not_called()

    def test_heartbeat_finishes_dissolved_group(self):
        now = int(time.time())
        path = _write_record(GROUP_ID, "2026-11-10_20-00-00", messages=[_msg(now - 60)])
        runtime_context.recording_sessions[GROUP_ID] = {
            "start": datetime.fromtimestamp(now - 600), "messages": [], "participants": {},
            "roles": {}, "dir": path, "img_count": 0,
        }
        plugin = self._plugin()
        with patch("plugins.trpg_session.fetch_group_list", return_value=set()):
            plugin._on_heartbeat()
        self.assertFalse(runtime_context.is_group_recording(GROUP_ID))
        self.assertEqual(self.meta(path)["end"], datetime.fromtimestamp(now - 60).strftime("%Y-%m-%d %H:%M:%S"))
        self.assertTrue((path / "record.md").is_file())

    def test_resume_banner_sent_once(self):
        class OkApi(MockApiWrapper):
            def __init__(self, ctx):
                super().__init__(ctx)
                self.calls = []

            def call_api(self, action, params):
                self.calls.append((action, params))
                return {"status": "ok"}

        session = {"start": datetime(2026, 11, 10, 20, 0), "messages": [], "participants": {},
                   "roles": {}, "dir": None, "img_count": 0, "resume_banner": True}
        runtime_context.recording_sessions[GROUP_ID] = session
        ctx = {"post_type": "meta"}
        plugin = TrpgSessionPlugin(ctx)
        plugin.api = OkApi(ctx)
        plugin._on_heartbeat()
        self.assertEqual([c[0] for c in plugin.api.calls], ["send_group_msg"])
        self.assertFalse(session["resume_banner"])
        with patch("plugins.trpg_session.fetch_group_list", return_value={GROUP_ID}):
            plugin._on_heartbeat()
        self.assertEqual(len(plugin.api.calls), 1)


# ── 规则选择与写入记录 ────────────────────────────────

class TestRule(IsolationMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.use_temp_data_path()

    def test_list_rules(self):
        self.patch_members([{"user_id": "111", "nickname": "玩家A", "is_robot": False}])
        out = _joined(_run([_text_seg("/跑团 规则")]))
        self.assertIn("当前规则：DND 5E", out)
        self.assertIn("COC 7th", out)

    def test_dm_sets_rule(self):
        self.seed_party()
        plugin = _run([_text_seg("/跑团 规则 coc7th")])
        self.assertIn("COC 7th", _sent_text(plugin))
        self.assertEqual(party.read_pending(GROUP_ID)["rules"], "coc7th")

    def test_non_dm_cannot_set_rule(self):
        self.patch_members([
            {"user_id": "111", "nickname": "玩家A", "is_robot": False},
            {"user_id": "222", "nickname": "玩家B", "is_robot": False},
        ])
        plugin = _run([_text_seg("/跑团 规则 coc7th")], user_id=222, nickname="玩家B")
        self.assertIn("只有 DM", _sent_text(plugin))

    def test_rule_refused_during_recording(self):
        _run([_text_seg("/跑团 记录 强制开始")])
        plugin = _run([_text_seg("/跑团 规则")])
        self.assertIn("录制中", _sent_text(plugin))

    def test_rule_written_into_meta_on_start(self):
        self.seed_party()
        _run([_text_seg("/跑团 规则 coc7th")], user_id=111, nickname="玩家A")
        _run([_text_seg("/跑团 记录 开始")])
        meta = self.meta(self.record_dir())
        self.assertEqual(meta["rules"], "coc7th")
        self.assertEqual(runtime_context.get_recording_session(GROUP_ID)["rules"], "coc7th")

    def test_unknown_rule_rejected(self):
        self.seed_party()
        plugin = _run([_text_seg("/跑团 规则 gurps")])
        self.assertIn("未知规则", _sent_text(plugin))
        self.assertEqual(party.read_pending(GROUP_ID)["rules"], "dnd5e")


class TestResumeRule(IsolationMixin, unittest.TestCase):
    def test_resume_restores_rule_from_meta(self):
        self.setUp()
        self.use_temp_data_path()
        import time as _time
        now = int(_time.time())
        path = records.group_dir(GROUP_ID) / "2026-11-10_20-00-00"
        (path / "imgs").mkdir(parents=True, exist_ok=True)
        records.rewrite_meta(path, {
            "version": 2, "group_id": GROUP_ID, "group_name": "夜航团",
            "start": "2026-11-10 20:00:00", "end": None, "rules": "coc7th",
            "roles": {}, "participants": [],
        })
        records.append_message(path, {
            "time": now - 60, "sender_type": "user", "user_id": "111",
            "nickname": "玩家A", "char_name": "", "role": "",
            "segments": [{"type": "text", "text": "hi"}],
        })
        with patch("plugins.trpg_session.fetch_group_list", return_value={GROUP_ID}):
            self.assertEqual(recover_recordings(), 1)
        self.assertEqual(runtime_context.get_recording_session(GROUP_ID)["rules"], "coc7th")


class TestPrepareRuleMatch(IsolationMixin, unittest.TestCase):
    """本团规则与当前角色卡规则不一致时拒绝准备。"""

    def setUp(self):
        super().setUp()
        self.use_temp_data_path()
        self.patch_members([{"user_id": "111", "nickname": "玩家A", "is_robot": False}])

    def test_mismatch_refused(self):
        party.set_rule(GROUP_ID, "coc7th")
        store.create_char("111", {"char_name": "艾伦", "rules": "dnd5e"})
        plugin = _run([_text_seg("/跑团 准备")])
        self.assertIn("本团规则是 COC 7th", _sent_text(plugin))
        self.assertEqual(party.read_pending(GROUP_ID)["prepared"], {})

    def test_matching_rule_accepted(self):
        party.set_rule(GROUP_ID, "coc7th")
        store.create_char("111", {"char_name": "田宫真莉", "rules": "coc7th", "occupation": "药剂师"})
        _run([_text_seg("/跑团 准备")])
        self.assertIn("111", party.read_pending(GROUP_ID)["prepared"])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestGrowth(IsolationMixin, unittest.TestCase):
    """幕间成长：/跑团 成长 只结算自己的卡，DM 可 @ 他人。"""

    def setUp(self):
        super().setUp()
        self.use_temp_data_path()

    def _seed_card(self, user_id="111", **over):
        card = {
            "rules": "coc7th", "char_name": "田宫", "occupation": "药剂师",
            "str_score": 60, "con_score": 55, "siz_score": 45, "dex_score": 55,
            "app_score": 60, "int_score": 85, "pow_score": 65, "edu_score": 45,
            "current_san": 65,
            "skills": {"侦察": {"base": 25, "growth": 0, "check": True},
                       "图书馆": {"base": 20, "growth": 0}},
        }
        card.update(over)
        char_id = store.create_char(user_id, card)
        store.set_current(user_id, char_id)
        return card

    def test_settles_checked_skills(self):
        self.seed_party()
        party.set_rule(GROUP_ID, "coc7th")
        self._seed_card()
        with patch("core.trpg.growth.random.randint", side_effect=[90, 4]):
            plugin = _run([_text_seg("/跑团 成长")])
        out = _sent_text(plugin)
        self.assertIn("幕间成长", out)
        self.assertIn("+4", out)
        self.assertIn("已清空", out)
        card = store.get_current("111")
        self.assertEqual(card["skills"]["侦察"]["growth"], 4)
        self.assertFalse(card["skills"]["侦察"]["check"])

    def test_no_marks_message(self):
        self.seed_party()
        party.set_rule(GROUP_ID, "coc7th")
        self._seed_card(skills={"侦察": {"base": 25, "growth": 0}})
        plugin = _run([_text_seg("/跑团 成长")])
        self.assertIn("没有已标记的技能", _sent_text(plugin))

    def test_dnd_card_refused(self):
        self.seed_party()
        self._seed_card(rules="dnd5e")
        plugin = _run([_text_seg("/跑团 成长")])
        self.assertIn("不是 COC 调查员卡", _sent_text(plugin))

    def test_group_rule_mismatch_refused(self):
        self.seed_party()
        self._seed_card()
        plugin = _run([_text_seg("/跑团 成长")])
        self.assertIn("本团规则是 DND 5E", _sent_text(plugin))

    def test_non_dm_cannot_target_other(self):
        self.patch_members([
            {"user_id": "111", "nickname": "玩家A", "is_robot": False},
            {"user_id": "222", "nickname": "玩家B", "is_robot": False},
        ])
        self._seed_card()
        _run([_text_seg("/跑团 规则 coc7th")], user_id=111, nickname="玩家A")
        plugin = _run([_text_seg("/跑团 成长"), {"type": "at", "data": {"qq": "111"}}],
                      user_id=222, nickname="玩家B")
        self.assertIn("只有 DM", _sent_text(plugin))


class TestSheetSnapshots(IsolationMixin, unittest.TestCase):
    """记录里的角色卡快照：开录存 sheet_start，结束存 sheet_end。"""

    def setUp(self):
        super().setUp()
        self.use_temp_data_path()

    def _card(self, user_id="111", **over):
        card = {
            "rules": "dnd5e", "char_name": "艾拉", "race": "人类", "class_name": "战士",
            "level": 3, "xp": 2700, "hp": 30, "current_hp": 22,
            "str_score": 15, "dex_score": 14, "con_score": 14,
            "int_score": 10, "wis_score": 10, "cha_score": 8,
        }
        card.update(over)
        char_id = store.create_char(user_id, card)
        store.set_current(user_id, char_id)
        return char_id

    def test_start_snapshot_written(self):
        self.seed_party()
        char_id = self._card()
        party.set_prepared(GROUP_ID, "111", {"user_id": "111", "char_id": char_id, "prepared_at": "2026-11-11 10:00:00"})
        _run([_text_seg("/跑团 记录 开始")])
        person = self.meta(self.record_dir())["participants"][0]
        self.assertEqual(person["char_id"], char_id)
        self.assertEqual(person["sheet_start"]["level"], 3)
        self.assertEqual(person["sheet_start"]["hp"], 30)

    def test_end_snapshot_written(self):
        self.seed_party()
        char_id = self._card()
        party.set_prepared(GROUP_ID, "111", {"user_id": "111", "char_id": char_id, "prepared_at": "2026-11-11 10:00:00"})
        _run([_text_seg("/跑团 记录 开始")])
        store.update_char("111", char_id, dict(store.get_char("111", char_id), level=4, hp=38))
        _run([_text_seg("/跑团 记录 结束")])
        person = self.meta(self.record_dir())["participants"][0]
        self.assertEqual(person["sheet_start"]["level"], 3)
        self.assertEqual(person["sheet_end"]["level"], 4)

    def test_deleted_card_keeps_start_snapshot(self):
        self.seed_party()
        char_id = self._card()
        party.set_prepared(GROUP_ID, "111", {"user_id": "111", "char_id": char_id, "prepared_at": "2026-11-11 10:00:00"})
        _run([_text_seg("/跑团 记录 开始")])
        store.delete_char("111", char_id)
        _run([_text_seg("/跑团 记录 结束")])
        person = self.meta(self.record_dir())["participants"][0]
        self.assertIn("sheet_start", person)
        self.assertNotIn("sheet_end", person)
