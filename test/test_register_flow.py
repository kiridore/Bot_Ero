"""community-registration AC1：注册流程逐句文案、持久化、播种、通知与边界。"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import config
from core.database_manager import DbManager
from core.event import Event
from core.feature_packs import FEATURE_PACKS
from core.message_output import MessageOutput
from core.plugin_dispatch import Operation
from plugins.register import RegisterPlugin, _SESSIONS, _STAGE_EULA_SENT

UID = 424242


def make_private(text_body, uid=UID):
    return {"post_type": "message", "message_type": "private", "user_id": uid,
            "message_id": 9, "message": [{"type": "text", "data": {"text": text_body}}]}


class RegisterFlowTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_db = config.DB_PATH
        config.DB_PATH = Path(self._tmp.name) / "reg.db"
        self.db = DbManager()
        self._old_pack = config.REGISTER_DEFAULT_PACK
        config.REGISTER_DEFAULT_PACK = "基础包"  # 会话配置为内置包表
        _SESSIONS.clear()
        # 隔离：目录可写（资料卡路径由 llonebot_data_path 决定，本测试不发卡）
        self.sent = []
        self.forwards = []
        self.sleeps = []

    def tearDown(self):
        self.db.conn.close()
        config.DB_PATH = self._old_db
        config.REGISTER_DEFAULT_PACK = self._old_pack
        _SESSIONS.clear()
        self._tmp.cleanup()

    def _plugin(self, text_body, published):
        raw = make_private(text_body)
        p = RegisterPlugin.__new__(RegisterPlugin)
        p.bot_event = Event(raw)
        p.dbmanager = self.db
        p.api = Mock()
        p.api.send_private_msg.side_effect = lambda seg: self.sent.append(seg["data"]["text"]) or 1
        p.api.send_forward_msg.side_effect = lambda message: self.forwards.append(message) or 1
        op = Operation({"register": True, "show_menu": True},
                       MessageOutput(lambda r: 1, ("private", UID)))
        op.publish = lambda topic, payload=None, **kw: published.append((topic, payload or kw))
        p.operation = op
        return p

    def _run(self, text_body, published=None):
        published = published if published is not None else []
        p = self._plugin(text_body, published)
        p.match("message")
        with patch("plugins.register.time.sleep", side_effect=lambda s: self.sleeps.append(s)):
            p.handle()
        return p

    def test_full_flow_exact_copy_and_pauses(self):
        published = []
        self._run("/注册", published)
        self.assertEqual(self.sent[0], "现在开始注册流程，大概需要5分钟~")
        self.assertEqual(self.sent[1], "首先需要阅读一下我们的《用户协议》，里面一定有很多你关心的内容，务必看过之后再同意哦")
        self.assertEqual(len(self.forwards), 1)
        self.assertIn("用户协议", self.forwards[0][0]["data"]["text"])
        self.assertEqual(self.sent[2], "如果看完后同意，请使用 “/同意EULA”指令继续")
        self.assertEqual(self.sleeps[:3], [self.sleeps[0], self.sleeps[1], 5])
        self.assertTrue(2 <= self.sleeps[0] <= 3 and 2 <= self.sleeps[1] <= 3)
        self.assertEqual(_SESSIONS.get(UID), _STAGE_EULA_SENT)
        self.assertEqual(published, [])  # 尚未注册完成，无通知

        self._run("/同意eula", published)  # 大小写不敏感
        self.assertEqual(self.sent[3], "太好了！感谢你的理解，那我先帮你登记*写写*")  # 星号原样
        self.assertEqual(self.sent[4], "完成啦，已经开放基础功能权限，更多功能会逐步开发中，用“/菜单”指令看看现在有什么吧~")
        self.assertEqual([t for t, _ in published], ["register.completed"])
        self.assertNotIn(UID, _SESSIONS)
        row = self.db.conn.execute(
            "SELECT eula_version, agreed_at FROM user_accounts WHERE user_id = ?", (UID,)).fetchone()
        self.assertEqual(row[0], "v1")
        self.assertIsNotNone(row[1])
        # 播种：打卡基础包成员获得账号开关
        members = set(FEATURE_PACKS["基础包"]["plugins"])
        seeded = {r[0] for r in self.db.conn.execute(
            "SELECT plugin_name FROM user_plugin_config WHERE user_id = ?", (UID,)).fetchall()}
        self.assertEqual(seeded, members)

    def test_group_chat_gets_hint_only(self):
        p = self._plugin("/注册", [])
        p.bot_event = Event({"post_type": "message", "message_type": "group", "user_id": UID,
                             "group_id": 10, "message_id": 9,
                             "message": [{"type": "text", "data": {"text": "/注册"}}]})
        p.match("message")
        p.handle()
        self.assertEqual(self.sent, ["请先添加我为好友，在私聊中完成注册~"])
        self.assertFalse(self.forwards)

    def test_case_insensitive_and_unknown_command(self):
        self.assertTrue(self._plugin("/同意EULA", []).match("message"))
        p = self._plugin("/同意eula", [])
        self.assertTrue(p.match("message"))
        self.assertEqual(p.cmd, "/同意EULA")
        p2 = self._plugin("/同意eulaa", [])
        self.assertFalse(p2.match("message"))

    def test_repeat_register_reruns_flow(self):
        self._run("/注册")
        self._run("/注册")  # 重复：从头重发
        self.assertEqual(len(self.forwards), 2)
        self.assertEqual(self.sent.count("现在开始注册流程，大概需要5分钟~"), 2)

    def test_agree_without_session_and_already_registered(self):
        self._run("/同意EULA")
        self.assertEqual(self.sent, ["先发 /注册 开始注册流程哦"])
        self.db.community.agree_eula(UID, "v1")
        self._run("/同意EULA")
        self.assertEqual(self.sent[-1], "你已经完成注册啦")
        self._run("/注册")
        self.assertEqual(self.sent[-1], "你已经完成注册啦")

    def test_restart_clears_session_but_keeps_registered(self):
        self._run("/注册")
        _SESSIONS.clear()  # 模拟重启：会话丢失
        self._run("/同意EULA")
        self.assertEqual(self.sent[-1], "先发 /注册 开始注册流程哦")  # 未同意=未同意（安全侧）


if __name__ == "__main__":
    unittest.main(verbosity=2)
