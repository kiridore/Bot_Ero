"""邮箱绑定验证码：进程内状态机（spec D6）+ 邮件模板 + 邮箱工具。

冷却/过期/作废均为进程内状态——仓库硬约束 webapp 单进程（禁 --workers），
重启丢码可接受（用户重发即可）。
"""

from __future__ import annotations

import re
import secrets
import threading
import time
from datetime import datetime

from core import mail_client
from core import user_settings as user_settings_mod

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CODE_TTL_SECONDS = 600
CODE_COOLDOWN_SECONDS = 60
MAX_ATTEMPTS = 5

_lock = threading.Lock()
# {(user_id, purpose): {"code","email","purpose","expires_at","attempts","last_sent_at"}}
# 键含 purpose：bind/unbind 各自独立冷却，切换目的不可绕过冷却
_pending: dict[tuple[str, str], dict] = {}
# bind 目标邮箱 → 最近发码时间（跨账号共享，防多账号轮换轰炸同一邮箱；unbind 不限，只发本人已验证邮箱）
_email_last_sent: dict[str, float] = {}


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email or ""))


def mask_email(email: str) -> str:
    if not email or "@" not in email:
        return email or ""
    local, _, domain = email.partition("@")
    head = local[:2] if len(local) > 2 else local[:1]
    return f"{head}***@{domain}"


def mail_enabled() -> bool:
    return mail_client._configured()


def _render_email_html(code: str) -> str:
    return (
        "<div style='font-family:sans-serif;max-width:420px;margin:0 auto;padding:24px;'>"
        "<h2 style='margin:0 0 16px;'>BotEro 邮箱验证码</h2>"
        f"<p style='font-size:34px;font-weight:bold;letter-spacing:8px;margin:0 0 16px;'>{code}</p>"
        "<p style='color:#666;margin:0 0 8px;'>有效期 10 分钟。</p>"
        "<p style='color:#999;margin:0;'>若非本人操作请忽略本邮件。</p>"
        "</div>"
    )


def issue_code(user_id: str, email: str, purpose: str, *, now: float | None = None) -> tuple[bool, str | None]:
    """发送验证码。冷却中 → (False, 提示)；发送失败 → (False, 原因) 并清状态。"""
    global _email_last_sent
    t = time.time() if now is None else now
    with _lock:
        key = (user_id, purpose)
        entry = _pending.get(key)
        if entry and t - entry["last_sent_at"] < CODE_COOLDOWN_SECONDS:
            remain = int(CODE_COOLDOWN_SECONDS - (t - entry["last_sent_at"])) + 1
            return False, f"发送太频繁，请 {remain} 秒后再试"
        if purpose == "bind" and t - _email_last_sent.get(email, 0) < CODE_COOLDOWN_SECONDS:
            return False, "该邮箱发送太频繁，请稍后再试"
        _email_last_sent = {
            e: ts for e, ts in _email_last_sent.items() if t - ts < CODE_COOLDOWN_SECONDS
        }
        code = f"{secrets.randbelow(1000000):06d}"
        _pending[key] = {
            "code": code,
            "email": email,
            "purpose": purpose,
            "expires_at": t + CODE_TTL_SECONDS,
            "attempts": 0,
            "last_sent_at": t,
        }
        if purpose == "bind":
            _email_last_sent[email] = t
    ok, msg = mail_client.send_email(
        to=[email],
        subject="BotEro 邮箱验证码",
        html=_render_email_html(code),
        text=f"验证码 {code}，10 分钟内有效。若非本人操作请忽略。",
    )
    if not ok:
        with _lock:
            _pending.pop(key, None)
        return False, f"邮件发送失败：{msg}"
    return True, None


def verify_code(
    user_id: str, email: str, code: str, purpose: str, *, now: float | None = None
) -> tuple[bool, str | None]:
    """校验并消费验证码（匹配 email+purpose+code 且未过期）。"""
    t = time.time() if now is None else now
    with _lock:
        entry = _pending.get((user_id, purpose))
        if entry is None:
            return False, "请先获取验证码"
        if t > entry["expires_at"]:
            del _pending[(user_id, purpose)]
            return False, "验证码已过期，请重新获取"
        if entry["email"] != email or entry["code"] != code:
            entry["attempts"] += 1
            if entry["attempts"] >= MAX_ATTEMPTS:
                del _pending[(user_id, purpose)]
                return False, "错误次数过多，验证码已作废，请重新获取"
            return False, "验证码不正确"
        del _pending[(user_id, purpose)]
    return True, None


def bind_email(user_id: str, email: str, code: str, *, now: float | None = None) -> tuple[bool, str | None]:
    ok, err = verify_code(user_id, email, code, "bind", now=now)
    if not ok:
        return False, err
    user_settings_mod.update_settings(user_id, {
        "email": email,
        "email_bound_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    return True, None


def unbind_email(user_id: str, code: str, *, now: float | None = None) -> tuple[bool, str | None]:
    current = user_settings_mod.get_settings(user_id).get("email")
    if not current:
        return False, "当前未绑定邮箱"
    ok, err = verify_code(user_id, current, code, "unbind", now=now)
    if not ok:
        return False, err
    user_settings_mod.update_settings(user_id, {"email": None, "email_bound_at": None})
    return True, None
