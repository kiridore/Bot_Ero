"""邮箱验证码状态机：签发/校验/过期/冷却/作废/脱敏（spec D3-D6）。"""

import unittest
from unittest import mock

from webapp.profile import email_service


def _issue(user, email, purpose="bind", now=1000.0):
    return email_service.issue_code(user, email, purpose, now=now)


def _code_of(user, purpose="bind"):
    return email_service._pending[(user, purpose)]["code"]


class EmailCodeServiceTest(unittest.TestCase):
    def setUp(self):
        email_service._pending.clear()
        email_service._email_last_sent.clear()

    def test_issue_and_verify_ok(self):
        with mock.patch.object(email_service.mail_client, "send_email") as send:
            send.return_value = (True, "")
            ok, err = _issue("10001", "a@example.com")
        self.assertTrue(ok)
        self.assertIsNone(err)
        send.assert_called_once()
        kwargs = send.call_args.kwargs
        self.assertEqual(kwargs["to"], ["a@example.com"])
        self.assertIn("验证码", kwargs["subject"])
        ok, err = email_service.verify_code(
            "10001", "a@example.com", _code_of("10001"), "bind", now=1000.5)
        self.assertTrue(ok)

    def test_verify_consumes_code(self):
        with mock.patch.object(email_service.mail_client, "send_email") as send:
            send.return_value = (True, "")
            _issue("10001", "a@example.com")
        code = _code_of("10001")
        self.assertTrue(email_service.verify_code("10001", "a@example.com", code, "bind", now=1000.5)[0])
        self.assertFalse(email_service.verify_code("10001", "a@example.com", code, "bind", now=1000.6)[0])

    def test_expired_code_rejected(self):
        with mock.patch.object(email_service.mail_client, "send_email") as send:
            send.return_value = (True, "")
            _issue("10001", "a@example.com", now=1000.0)
        ok, err = email_service.verify_code(
            "10001", "a@example.com", _code_of("10001"), "bind", now=1000.0 + 601)
        self.assertFalse(ok)
        self.assertIn("过期", err)

    def test_cooldown_blocks_then_allows(self):
        with mock.patch.object(email_service.mail_client, "send_email") as send:
            send.return_value = (True, "")
            self.assertTrue(_issue("10001", "a@example.com", now=1000.0)[0])
            ok, err = _issue("10001", "other@example.com", now=1030.0)
            self.assertFalse(ok)
            self.assertIn("频繁", err)
            self.assertTrue(_issue("10001", "other@example.com", now=1061.0)[0])  # 冷却后重发覆盖
            # 校验必须用最新邮箱的码
            self.assertFalse(email_service.verify_code(
                "10001", "a@example.com", "000000", "bind", now=1062.0)[0])

    def test_wrong_code_void_after_five(self):
        with mock.patch.object(email_service.mail_client, "send_email") as send:
            send.return_value = (True, "")
            _issue("10001", "a@example.com")
        code = _code_of("10001")
        for i in range(4):
            ok, err = email_service.verify_code("10001", "a@example.com", "000000", "bind", now=1000.5)
            self.assertFalse(ok)
            self.assertIn("不正确", err)
        ok, err = email_service.verify_code("10001", "a@example.com", "000000", "bind", now=1000.5)
        self.assertFalse(ok)
        self.assertIn("作废", err)
        # 作废后正确码也不可用
        self.assertFalse(email_service.verify_code(
            "10001", "a@example.com", code, "bind", now=1000.6)[0])

    def test_send_failure_cleans_state(self):
        with mock.patch.object(email_service.mail_client, "send_email") as send:
            send.return_value = (False, "SMTP down")
            ok, err = _issue("10001", "a@example.com")
        self.assertFalse(ok)
        self.assertIn("邮件发送失败", err)
        self.assertNotIn(("10001", "bind"), email_service._pending)

    def test_purpose_mismatch_rejected(self):
        with mock.patch.object(email_service.mail_client, "send_email") as send:
            send.return_value = (True, "")
            _issue("10001", "a@example.com", purpose="unbind")
        self.assertFalse(email_service.verify_code(
            "10001", "a@example.com", _code_of("10001", "unbind"), "bind", now=1000.5)[0])

    def test_purpose_alternation_does_not_bypass_cooldown(self):
        with mock.patch.object(email_service.mail_client, "send_email") as send:
            send.return_value = (True, "")
            self.assertTrue(_issue("10001", "a@example.com", now=1000.0)[0])
            # 不同 purpose 独立条目 → 不受 bind 冷却限制
            self.assertTrue(_issue("10001", "a@example.com", purpose="unbind", now=1005.0)[0])
            # 交替回 bind：t=1000 的 bind 冷却仍生效
            ok, err = _issue("10001", "a@example.com", now=1010.0)
            self.assertFalse(ok)
            self.assertIn("频繁", err)
            self.assertTrue(_issue("10001", "a@example.com", now=1061.0)[0])

    def test_bind_email_rate_limit_per_email(self):
        with mock.patch.object(email_service.mail_client, "send_email") as send:
            send.return_value = (True, "")
            self.assertTrue(_issue("A", "v@x.com", now=1000.0)[0])
            # 另一账号发同一目标邮箱 → 被目标邮箱限频拦截
            ok, err = _issue("B", "v@x.com", now=1010.0)
            self.assertFalse(ok)
            self.assertIn("该邮箱发送太频繁", err)
            # 不同目标邮箱不受影响
            self.assertTrue(_issue("B", "w@y.com", now=1010.0)[0])
            # unbind 豁免：_pending 清空、_email_last_sent 仍含 v@x.com
            email_service._pending.clear()
            ok, err = _issue("C", "v@x.com", purpose="unbind", now=1010.0)
            self.assertTrue(ok)
            # bind 到 v@x.com 仍被拦截（同一 C 用户也未豁免）
            self.assertFalse(_issue("C", "v@x.com", now=1010.0)[0])

    def test_mask_and_validate(self):
        self.assertEqual(email_service.mask_email("abcd@qq.com"), "ab***@qq.com")
        self.assertEqual(email_service.mask_email("x@qq.com"), "x***@qq.com")
        self.assertEqual(email_service.mask_email(""), "")
        self.assertTrue(email_service.is_valid_email("a.b@c.d"))
        self.assertFalse(email_service.is_valid_email("a@b"))
        self.assertFalse(email_service.is_valid_email("a b@c.d"))
        self.assertFalse(email_service.is_valid_email(""))


if __name__ == "__main__":
    unittest.main()
