"""测试 redeem_code 提示桩插件：撤回指令消息＋引导网页个人主页。

运行: pytest test/test_redeem_code_stub.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from plugins.redeem_code import RedeemCodePlugin
from test.helper import MockApiWrapper, make_group_message, make_private_message


def _sent_text(plugin) -> str:
    """取插件发出的唯一一条消息的文本段（可能前置 at 段）。"""
    assert len(plugin.api.sent_messages) == 1, "预期只发一条消息"
    segments = plugin.api.sent_messages[0][1]
    return next(seg["data"]["text"] for seg in segments if seg.get("type") == "text")


class TestRedeemCodeStub(unittest.TestCase):
    def test_match_accepts_command(self):
        for text in ("/兑换码", "/兑换码 BEST-WISH-2027", "/兌換碼"):
            self.assertTrue(RedeemCodePlugin(make_group_message(text)).match("message"), text)

    def test_match_rejects_non_command(self):
        for text in ("/兑换", "兑换码 BEST-WISH-2027", "你好", "/商店"):
            self.assertFalse(RedeemCodePlugin(make_group_message(text)).match("message"), text)

    def test_handle_recalls_and_tips_group(self):
        ctx = make_group_message("/兑换码 BEST-WISH-2027", message_id=4242)
        plugin = RedeemCodePlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        self.assertEqual(plugin.api.deleted_messages, [4242])
        self.assertEqual(_sent_text(plugin), "兑换码功能已迁移至网页个人主页「兑换码」页签")

    def test_handle_tips_even_if_recall_fails(self):
        ctx = make_group_message("/兑换码", message_id=99)
        plugin = RedeemCodePlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.api.delete_msg_ok = False
        plugin.handle()
        self.assertEqual(plugin.api.deleted_messages, [99])
        self.assertIn("已迁移至网页个人主页", _sent_text(plugin))

    def test_handle_private_chat_attempts_recall_and_tips(self):
        ctx = make_private_message("/兌換碼 BEST-WISH-2027", message_id=7)
        plugin = RedeemCodePlugin(ctx)
        plugin.api = MockApiWrapper(ctx)
        plugin.handle()
        self.assertEqual(plugin.api.deleted_messages, [7])
        self.assertIn("「兑换码」页签", _sent_text(plugin))


if __name__ == "__main__":
    unittest.main()
