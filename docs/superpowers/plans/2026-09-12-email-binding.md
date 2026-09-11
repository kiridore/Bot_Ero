# 邮箱绑定 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 设置页可绑定/换绑/解绑邮箱：6 位验证码（10 分钟有效、60s 冷却、错 5 次作废）经 cloud-mail 发送，绑定结果存 `user_settings`。

**Architecture:** 新 `webapp/profile/email_service.py` 承载进程内验证码状态机（dict+锁）与邮件模板；`app.py` 加 3 个路由并扩展 `SettingsOut.email`；`settings.js` 新增「账号邮箱」卡片三态渲染；测试分纯逻辑单测（进程内）+ API 脚本套件（TestClient + monkeypatch 发信）。

**Tech Stack:** FastAPI 同步路由 + `core/mail_client.py`（既有）+ `core/user_settings.py`（既有深合并）+ 原生 JS/CSS。

**Spec:** `docs/superpowers/specs/2026-09-12-email-binding-design.md`

## Global Constraints

- **Commit 纪律（覆盖 skill 默认逐任务提交）**：仓库惯例一特性一 commit（先例 `b852c20`）。Task 1–3 照常 commit 供审查出 diff；Task 4 最终提交前 `git reset --soft <BASE>` squash 成唯一 feature commit。
- bot 进程禁止 async/await；webapp 同步 `def` 路由合法。
- 所有新路由挂 `Depends(get_current_user_id)`；路径常量用 `config.X` 属性访问、禁止导入期绑定。
- 测试脚本 MUST 用 `test/scripts/_env.py::write_config` 生成临时配置经 `BOTERO_CONFIG` 指向，绝不触真实 `server_data`。
- 验证码状态只在 webapp 进程内（仓库禁止 `--workers`，单进程假设成立，spec D6）。
- `email_service` 引用邮件模块用 `from core import mail_client` 后 `mail_client.send_email(...)`（模块属性调用，测试可 monkeypatch）。
- 版本：`core/config.py::BOTERO_VERSION` `1.46.0` → `1.47.0`（minor）。
- 前端改动若触 `core/web/static/profile.css` 需 bump settings.html 的 `?v=`（当前无 v 参数，本特性不动该 css 时无需 bump）。
- 用户可见文案同 commit 更新测试断言（脚本套件断言 API 文案）。

---

### Task 1: 验证码状态机服务 + 纯逻辑单测

**Files:**
- Create: `webapp/profile/email_service.py`
- Test: `test/test_email_code_service.py`

**Interfaces:**
- Consumes: `core.mail_client.send_email(to, subject, html, text=None, sender_name=None, ...) -> tuple[bool, str]`、`core.user_settings.get_settings/update_settings`
- Produces（Task 2 路由依赖，签名逐字）：
  - `is_valid_email(email: str) -> bool`
  - `mask_email(email: str) -> str`
  - `mail_enabled() -> bool`
  - `issue_code(user_id: str, email: str, purpose: str, *, now: float | None = None) -> tuple[bool, str | None]`
  - `bind_email(user_id: str, email: str, code: str, *, now: float | None = None) -> tuple[bool, str | None]`
  - `unbind_email(user_id: str, code: str, *, now: float | None = None) -> tuple[bool, str | None]`
  - 常量 `CODE_COOLDOWN_SECONDS = 60`

- [ ] **Step 1: 写失败的单测**

创建 `test/test_email_code_service.py`（进程内 unittest；monkeypatch `mail_client.send_email`；`now` 参数驱动时间）：

```python
"""邮箱验证码状态机：签发/校验/过期/冷却/作废/脱敏（spec D3-D6）。"""

import unittest
from unittest import mock

from webapp.profile import email_service


def _issue(user, email, purpose="bind", now=1000.0):
    return email_service.issue_code(user, email, purpose, now=now)


def _code_of(user):
    return email_service._pending[user]["code"]


class EmailCodeServiceTest(unittest.TestCase):
    def setUp(self):
        email_service._pending.clear()

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
        self.assertTrue(email_service.verify_code("10001", "a@example.com", code, "bind")[0])
        self.assertFalse(email_service.verify_code("10001", "a@example.com", code, "bind")[0])

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
        for i in range(4):
            ok, err = email_service.verify_code("10001", "a@example.com", "000000", "bind")
            self.assertFalse(ok)
            self.assertIn("不正确", err)
        ok, err = email_service.verify_code("10001", "a@example.com", "000000", "bind")
        self.assertFalse(ok)
        self.assertIn("作废", err)
        # 作废后正确码也不可用
        self.assertFalse(email_service.verify_code(
            "10001", "a@example.com", _code_of("10001"), "bind")[0])

    def test_send_failure_cleans_state(self):
        with mock.patch.object(email_service.mail_client, "send_email") as send:
            send.return_value = (False, "SMTP down")
            ok, err = _issue("10001", "a@example.com")
        self.assertFalse(ok)
        self.assertIn("邮件发送失败", err)
        self.assertNotIn("10001", email_service._pending)

    def test_purpose_mismatch_rejected(self):
        with mock.patch.object(email_service.mail_client, "send_email") as send:
            send.return_value = (True, "")
            _issue("10001", "a@example.com", purpose="unbind")
        self.assertFalse(email_service.verify_code(
            "10001", "a@example.com", _code_of("10001"), "bind")[0])

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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest test/test_email_code_service.py -v`
Expected: FAIL（`ModuleNotFoundError`/`ImportError: webapp.profile.email_service`）

- [ ] **Step 3: 实现服务**

创建 `webapp/profile/email_service.py`：

```python
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
# {user_id: {"code","email","purpose","expires_at","attempts","last_sent_at"}}
_pending: dict[str, dict] = {}


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
    t = time.time() if now is None else now
    with _lock:
        entry = _pending.get(user_id)
        if (
            entry
            and entry["purpose"] == purpose
            and t - entry["last_sent_at"] < CODE_COOLDOWN_SECONDS
        ):
            remain = int(CODE_COOLDOWN_SECONDS - (t - entry["last_sent_at"])) + 1
            return False, f"发送太频繁，请 {remain} 秒后再试"
        code = f"{secrets.randbelow(1000000):06d}"
        _pending[user_id] = {
            "code": code,
            "email": email,
            "purpose": purpose,
            "expires_at": t + CODE_TTL_SECONDS,
            "attempts": 0,
            "last_sent_at": t,
        }
    ok, msg = mail_client.send_email(
        to=[email],
        subject="BotEro 邮箱验证码",
        html=_render_email_html(code),
        text=f"验证码 {code}，10 分钟内有效。若非本人操作请忽略。",
    )
    if not ok:
        with _lock:
            _pending.pop(user_id, None)
        return False, f"邮件发送失败：{msg}"
    return True, None


def verify_code(
    user_id: str, email: str, code: str, purpose: str, *, now: float | None = None
) -> tuple[bool, str | None]:
    """校验并消费验证码（匹配 email+purpose+code 且未过期）。"""
    t = time.time() if now is None else now
    with _lock:
        entry = _pending.get(user_id)
        if entry is None:
            return False, "请先获取验证码"
        if t > entry["expires_at"]:
            del _pending[user_id]
            return False, "验证码已过期，请重新获取"
        if entry["purpose"] != purpose or entry["email"] != email or entry["code"] != code:
            entry["attempts"] += 1
            if entry["attempts"] >= MAX_ATTEMPTS:
                del _pending[user_id]
                return False, "错误次数过多，验证码已作废，请重新获取"
            return False, "验证码不正确"
        del _pending[user_id]
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest test/test_email_code_service.py -v`
Expected: 8 passed

- [ ] **Step 5: commit（供审查，Task 4 会 squash）**

```bash
git add webapp/profile/email_service.py test/test_email_code_service.py
git commit -m "feat(个人中心): 邮箱验证码状态机服务与单测"
```

---

### Task 2: 三个 API 路由 + SettingsOut 扩展 + 脚本套件

**Files:**
- Modify: `webapp/profile/app.py`（import 区、`SettingsOut`、两个 settings 路由、新增 3 路由）
- Test: `test/scripts/check_profile_email_bind.py`（新建，`test_webapp_api_suites.py` 自动发现）

**Interfaces:**
- Consumes: Task 1 全部函数；既有 `api_my_settings`/`api_update_settings`
- Produces（Task 3 前端依赖）：
  - `POST /api/me/email/code` `{email, purpose}` → 200 `{"cooldown_seconds": 60}` / 400（格式/未绑定/冷却/发送失败，detail 中文）/ 503（mail 未配置）
  - `POST /api/me/email/bind` `{email, code}` → 200 `{"success": true}` / 400
  - `POST /api/me/email/unbind` `{code}` → 200 `{"success": true}` / 400
  - `GET/PUT /api/me/settings` 响应新增 `email`（未绑定为 null）

- [ ] **Step 1: 写失败的脚本套件**

创建 `test/scripts/check_profile_email_bind.py`：

```python
"""邮箱绑定 API 回归：发码/绑定/换绑/解绑/冷却/错码作废/503（spec D3-D5, D8）。

独立进程运行: python test/scripts/check_profile_email_bind.py
（pytest 由 test/test_webapp_api_suites.py 子进程自动纳入统一回归）
"""

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_email_bind_")
sys.path.insert(0, str(PROJECT_ROOT / "test" / "scripts"))
from _env import write_config  # noqa: E402

os.environ["BOTERO_CONFIG"] = write_config(_tmp)  # mail 节默认空 = 功能关闭

from fastapi.testclient import TestClient  # noqa: E402
from core.auth import make_login_key  # noqa: E402
from webapp.app import app  # noqa: E402
from webapp.profile import email_service  # noqa: E402

ME = "12345601"
MH = {"Authorization": "Bearer " + make_login_key(int(ME))}
client = TestClient(app)
fail = 0
sent: list[dict] = []


def check(name, ok, extra=""):
    global fail
    print(f"{'ok' if ok else 'FAIL'} - {name}" + (f" {extra}" if extra else ""))
    if not ok:
        fail += 1


def fake_send(to, subject, html, text=None, sender_name=None, attachments=None):
    sent.append({"to": to, "subject": subject, "html": html})
    return True, ""


def last_code():
    import re
    m = re.search(r"\d{6}", sent[-1]["html"])
    return m.group(0) if m else ""


# --- mail 未配置：503（真实 _configured()=False，config mail 节为空） ---
r = client.post("/api/me/email/code", headers=MH, json={"email": "a@b.com", "purpose": "bind"})
check("mail 未配置 503", r.status_code == 503, str(r.status_code))

# --- 打开邮件功能（monkeypatch 模块属性，不发真邮件） ---
email_service.mail_enabled = lambda: True
email_service.mail_client.send_email = fake_send

# --- 邮箱格式 400 ---
r = client.post("/api/me/email/code", headers=MH, json={"email": "not-an-email", "purpose": "bind"})
check("邮箱格式 400", r.status_code == 400 and "格式" in r.json()["detail"], r.text)

# --- 发码 → 冷却 → 绑定成功 ---
r = client.post("/api/me/email/code", headers=MH, json={"email": "alice@qq.com", "purpose": "bind"})
check("发码 200", r.status_code == 200 and r.json().get("cooldown_seconds") == 60, r.text)
check("邮件发往目标邮箱", sent and sent[-1]["to"] == ["alice@qq.com"])
# 冷却：同一未消费码的 60s 内重发 → 400（此时条目仍在）
r = client.post("/api/me/email/code", headers=MH, json={"email": "alice@qq.com", "purpose": "bind"})
check("冷却期重发 400", r.status_code == 400 and "频繁" in r.json()["detail"], r.text)
r = client.post("/api/me/email/bind", headers=MH, json={"email": "alice@qq.com", "code": last_code()})
check("绑定 200", r.status_code == 200, r.text)
r = client.get("/api/me/settings", headers=MH)
check("settings 返回 email", r.json().get("email") == "alice@qq.com", r.text)
check("settings 返回 email_bound_at", bool(r.json().get("email_bound_at")))

# --- 换邮箱重新发码（旧码已消费，条目已清 → 不受冷却限制） → 错码/错邮箱 → 换绑成功 ---
r = client.post("/api/me/email/code", headers=MH, json={"email": "bob@163.com", "purpose": "bind"})
check("旧码消费后重新发码 200", r.status_code == 200, r.text)
r = client.post("/api/me/email/bind", headers=MH, json={"email": "wrong@qq.com", "code": last_code()})
check("email 与码不匹配 400", r.status_code == 400 and "不正确" in r.json()["detail"], r.text)
r = client.post("/api/me/email/bind", headers=MH, json={"email": "bob@163.com", "code": "000000"})
check("错码 400", r.status_code == 400 and "不正确" in r.json()["detail"], r.text)
r = client.post("/api/me/email/bind", headers=MH, json={"email": "bob@163.com", "code": last_code()})
check("换绑 200", r.status_code == 200, r.text)
r = client.get("/api/me/settings", headers=MH)
check("settings email 已覆盖", r.json().get("email") == "bob@163.com", r.text)

# --- 解绑流程 ---
r = client.post("/api/me/email/code", headers=MH, json={"email": "x@x.com", "purpose": "unbind"})
check("unbind 发码 200（忽略入参 email，发当前邮箱）", r.status_code == 200 and sent[-1]["to"] == ["bob@163.com"], r.text)
r = client.post("/api/me/email/unbind", headers=MH, json={"code": last_code()})
check("解绑 200", r.status_code == 200, r.text)
r = client.get("/api/me/settings", headers=MH)
check("解绑后 email 为 null", r.json().get("email") is None, r.text)

# --- 解绑前提：已绑定 ---
email_service._pending.pop(ME, None)
r = client.post("/api/me/email/code", headers=MH, json={"email": "x@x.com", "purpose": "unbind"})
check("未绑定时 unbind 发码 400", r.status_code == 400 and "未绑定" in r.json()["detail"], r.text)

# --- 未登录 401 / purpose 非法 400 ---
r = client.post("/api/me/email/code", json={"email": "a@b.com", "purpose": "bind"})
check("未登录 401", r.status_code == 401, str(r.status_code))
r = client.post("/api/me/email/code", headers=MH, json={"email": "a@b.com", "purpose": "hack"})
check("purpose 非法 400", r.status_code == 400, r.text)

print(f"\n{'PASS' if fail == 0 else 'FAIL'}: {fail} failures")
sys.exit(0 if fail == 0 else 1)
```

- [ ] **Step 2: 跑套件确认失败**

Run: `python test/scripts/check_profile_email_bind.py`
Expected: 多项 FAIL（404：路由不存在）

- [ ] **Step 3: 实现路由**

`webapp/profile/app.py` 修改：

import 区新增（与其他 profile 服务 import 并列）：

```python
from webapp.profile import email_service
```

`SettingsOut` 扩展（原 `privacy: dict` 一行后加字段）：

```python
class SettingsOut(BaseModel):
    privacy: dict
    email: str | None = None
```

`SettingsIn` 后追加请求模型：

```python
class EmailCodeIn(BaseModel):
    email: str = ""
    purpose: str = "bind"


class EmailBindIn(BaseModel):
    email: str
    code: str


class EmailUnbindIn(BaseModel):
    code: str
```

`api_my_settings` / `api_update_settings` 两处返回值补 `email=` 字段：

```python
    return SettingsOut(privacy=settings.get("privacy", {}), email=settings.get("email"))
```
```python
    return SettingsOut(privacy=merged.get("privacy", {}), email=merged.get("email"))
```

`api_my_settings` 路由后新增三个路由：

```python
@router.post("/api/me/email/code")
def api_email_code(
    body: EmailCodeIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    if body.purpose not in ("bind", "unbind"):
        raise HTTPException(status_code=400, detail="purpose 不合法")
    if not email_service.mail_enabled():
        raise HTTPException(status_code=503, detail="邮件功能未开启，请联系管理员")
    if body.purpose == "bind":
        email = body.email.strip()
        if not email_service.is_valid_email(email):
            raise HTTPException(status_code=400, detail="邮箱格式不正确")
    else:
        email = user_settings_mod.get_settings(user_id).get("email") or ""
        if not email:
            raise HTTPException(status_code=400, detail="当前未绑定邮箱")
    ok, err = email_service.issue_code(user_id, email, body.purpose)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    return {"cooldown_seconds": email_service.CODE_COOLDOWN_SECONDS}


@router.post("/api/me/email/bind")
def api_email_bind(
    body: EmailBindIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    email = body.email.strip()
    if not email_service.is_valid_email(email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    ok, err = email_service.bind_email(user_id, email, body.code.strip())
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    return {"success": True}


@router.post("/api/me/email/unbind")
def api_email_unbind(
    body: EmailUnbindIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    ok, err = email_service.unbind_email(user_id, body.code.strip())
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    return {"success": True}
```

（`user_settings_mod` 已在 app.py import 为 `from core import user_settings as user_settings_mod`。）

- [ ] **Step 4: 跑套件确认通过**

Run: `python test/scripts/check_profile_email_bind.py`
Expected: 全部 ok，`PASS: 0 failures`

- [ ] **Step 5: 跑相关回归**

Run: `python -m pytest test/test_webapp_api_suites.py test/test_email_code_service.py -q`
Expected: 全部 passed

- [ ] **Step 6: commit**

```bash
git add webapp/profile/app.py test/scripts/check_profile_email_bind.py
git commit -m "feat(个人中心): 邮箱绑定与解绑API"
```

---

### Task 3: 设置页「账号邮箱」卡片

**Files:**
- Modify: `webapp/static/settings.js`（顶部状态 + 新函数群 + `renderPage` 插一行）
- Modify: `core/web/static/profile.css`（追加邮箱卡片样式）
- Modify: `webapp/static/settings.html`（css `?v=` bump：`/shared/profile.css` → `/shared/profile.css?v=2`）

**Interfaces:**
- Consumes: Task 2 三个 API + `GET /api/me/settings.email`；既有 `apiFetch/showToast/escapeHtml/renderPage/userSettingsData`
- Produces: DOM = `.email-form`（`#bindEmailInput/#bindSendBtn/#bindCodeInput/#bindSubmitBtn/#unbindCodeInput/#unbindSendBtn/#unbindSubmitBtn`）、`.email-bound-info`、`.email-actions`

- [ ] **Step 1: profile.css 追加样式（文件末尾）**

```css
/* ---- 账号邮箱卡片 ---- */
.email-bound-info {
  margin: 0 0 0.75rem;
  color: var(--ink);
}

.email-actions {
  display: flex;
  gap: 0.5rem;
}

.email-form-row {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.6rem;
  align-items: center;
}

.email-form-row input {
  flex: 1;
  min-width: 0;
}

.email-btn {
  padding: 0.45rem 1rem;
  font-size: 0.85rem;
  border-radius: 999px;
  border: 1px solid var(--rule);
  background: var(--paper-card);
  color: var(--ink-soft);
  cursor: pointer;
  white-space: nowrap;
}

.email-btn.primary {
  border-color: var(--accent);
  color: var(--accent);
}

.email-btn:disabled {
  opacity: 0.6;
  cursor: default;
}
```

（`input` 基础样式沿用 `.settings-section input` 既有规则；若选择器未覆盖 `input[type=email]`，复用 `.privacy-row input` 的视觉即可，不新增全局规则。）

- [ ] **Step 2: settings.js 顶部状态区追加**

`let searchQuery = "";` 后：

```js
let emailMode = "view"; // view | bind | unbind
let emailCooldownTimer = null;
```

- [ ] **Step 3: settings.js 新增函数群（放在 `buildCheckinDisplayRow` 之后）**

```js
function maskEmail(email) {
  const at = email.indexOf("@");
  if (at < 1) return email;
  const local = email.slice(0, at);
  return (local.length > 2 ? local.slice(0, 2) : local.slice(0, 1)) + "***" + email.slice(at);
}

function startEmailCooldown(btn, seconds) {
  if (emailCooldownTimer) clearInterval(emailCooldownTimer);
  btn.disabled = true;
  let left = seconds;
  const tick = () => {
    btn.textContent = `${left} 秒后可重发`;
    left -= 1;
    if (left < 0) {
      clearInterval(emailCooldownTimer);
      emailCooldownTimer = null;
      btn.disabled = false;
      btn.textContent = "发送验证码";
    }
  };
  tick();
  emailCooldownTimer = setInterval(tick, 1000);
}

async function sendEmailCode(purpose) {
  const btn = document.getElementById(purpose === "unbind" ? "unbindSendBtn" : "bindSendBtn");
  if (btn && btn.disabled) return;
  const email = purpose === "bind" ? (document.getElementById("bindEmailInput")?.value.trim() || "") : "";
  try {
    const res = await apiFetch("/api/me/email/code", {
      method: "POST",
      body: JSON.stringify({ email, purpose }),
    });
    showToast("验证码已发送，请查收邮箱");
    if (btn) startEmailCooldown(btn, res.cooldown_seconds || 60);
  } catch (err) {
    showToast(err.message, true);
  }
}

async function submitEmailBind() {
  const email = document.getElementById("bindEmailInput").value.trim();
  const code = document.getElementById("bindCodeInput").value.trim();
  try {
    await apiFetch("/api/me/email/bind", {
      method: "POST",
      body: JSON.stringify({ email, code }),
    });
    showToast("邮箱绑定成功");
    await reloadEmailState();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function submitEmailUnbind() {
  const code = document.getElementById("unbindCodeInput").value.trim();
  try {
    await apiFetch("/api/me/email/unbind", {
      method: "POST",
      body: JSON.stringify({ code }),
    });
    showToast("邮箱已解绑");
    await reloadEmailState();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function reloadEmailState() {
  userSettingsData = await apiFetch("/api/me/settings");
  emailMode = "view";
  renderPage();
}

function wireEmailForm(root) {
  const bindSend = root.querySelector("#bindSendBtn");
  const bindSubmit = root.querySelector("#bindSubmitBtn");
  const unbindSend = root.querySelector("#unbindSendBtn");
  const unbindSubmit = root.querySelector("#unbindSubmitBtn");
  const cancel = root.querySelector("#emailCancelBtn");
  if (bindSend) bindSend.addEventListener("click", () => sendEmailCode("bind"));
  if (bindSubmit) bindSubmit.addEventListener("click", submitEmailBind);
  if (unbindSend) unbindSend.addEventListener("click", () => sendEmailCode("unbind"));
  if (unbindSubmit) unbindSubmit.addEventListener("click", submitEmailUnbind);
  if (cancel) cancel.addEventListener("click", () => {
    emailMode = "view";
    renderPage();
  });
}

function renderEmailSection() {
  const sec = document.createElement("section");
  sec.className = "settings-section";
  const bound = userSettingsData.email;
  let body = "";
  if (bound && emailMode === "view") {
    body = `
      <p class="email-bound-info">已绑定：${escapeHtml(maskEmail(bound))}${
        userSettingsData.email_bound_at ? `（${escapeHtml(userSettingsData.email_bound_at)}）` : ""
      }</p>
      <div class="email-actions">
        <button type="button" class="email-btn primary" id="emailRebindBtn">换绑邮箱</button>
        <button type="button" class="email-btn" id="emailUnbindBtn">解绑邮箱</button>
      </div>
    `;
  } else if (emailMode === "unbind" && bound) {
    body = `
      <p class="email-bound-info">将向 ${escapeHtml(maskEmail(bound))} 发送验证码，输入后确认解绑。</p>
      <div class="email-form-row">
        <input type="text" id="unbindCodeInput" placeholder="6 位验证码" maxlength="6" inputmode="numeric" />
        <button type="button" class="email-btn" id="unbindSendBtn">发送验证码</button>
      </div>
      <div class="email-form-row">
        <button type="button" class="email-btn primary" id="unbindSubmitBtn">确认解绑</button>
        <button type="button" class="email-btn" id="emailCancelBtn">取消</button>
      </div>
    `;
  } else {
    body = `
      <div class="email-form-row">
        <input type="email" id="bindEmailInput" placeholder="输入要绑定的邮箱" />
        <button type="button" class="email-btn" id="bindSendBtn">发送验证码</button>
      </div>
      <div class="email-form-row">
        <input type="text" id="bindCodeInput" placeholder="6 位验证码" maxlength="6" inputmode="numeric" />
        <button type="button" class="email-btn primary" id="bindSubmitBtn">绑定</button>
      </div>
      <p class="preview-hint">验证码 10 分钟内有效。${bound ? "换绑成功后旧邮箱即被覆盖。" : ""}</p>
      ${bound ? '<div class="email-form-row"><button type="button" class="email-btn" id="emailCancelBtn">取消</button></div>' : ""}
    `;
  }
  sec.innerHTML = `<div class="section-head"><h2>账号邮箱</h2></div>${body}`;
  wireEmailForm(sec);
  const rebind = sec.querySelector("#emailRebindBtn");
  const unbind = sec.querySelector("#emailUnbindBtn");
  if (rebind) rebind.addEventListener("click", () => {
    emailMode = "bind";
    renderPage();
  });
  if (unbind) unbind.addEventListener("click", () => {
    emailMode = "unbind";
    renderPage();
  });
  return sec;
}
```

- [ ] **Step 4: renderPage 插入卡片**

`settingsMain.appendChild(renderThemeSection());` 一行后插入：

```js
  settingsMain.appendChild(renderEmailSection());
```

- [ ] **Step 5: settings.html bump css 版本**

`<link rel="stylesheet" href="/shared/profile.css" />` → `<link rel="stylesheet" href="/shared/profile.css?v=2" />`

- [ ] **Step 6: 验证**

Run: `node --check webapp/static/settings.js`
Expected: 无输出

Run: `python -m pytest test/test_webapp_api_suites.py -q`
Expected: passed（前端改动不影响 API）

- [ ] **Step 7: commit**

```bash
git add webapp/static/settings.js webapp/static/settings.html core/web/static/profile.css
git commit -m "feat(个人中心): 设置页邮箱绑定卡片"
```

---

### Task 4: 文档同步 + 版本 bump + squash 唯一 commit

**Files:**
- Modify: `CHANGELOG.md`（顶部新增 `[1.47.0]` 节）
- Modify: `core/config.py`（`BOTERO_VERSION = "1.47.0"`）
- Modify: `specs/web-gallery.md`（`/api/me` 路由表加 3 行 + settings 行补 email 字段说明）
- Commit: Task 1–4 全部文件 squash 为一个

**Interfaces:**
- Consumes: Task 1–3 全部产物
- Produces: master 上的单一 feature commit

- [ ] **Step 1: CHANGELOG**

`# 更新日志` 说明段后、`## [1.46.0]` 之前插入：

```markdown
## [1.47.0]

- **个人中心邮箱绑定**：设置页新增「账号邮箱」卡片，绑定/换绑/解绑均经邮箱验证码确认（6 位数字、10 分钟有效、60 秒发送冷却、错 5 次作废）；验证邮件经 cloud-mail 发送（`config.yaml mail` 节未配置时提示功能未开启）；绑定结果存个人设置，`GET /api/me/settings` 新增 `email` 字段
```

- [ ] **Step 2: 版本 bump**

`core/config.py`：`BOTERO_VERSION = "1.46.0"` → `"1.47.0"`

- [ ] **Step 3: specs/web-gallery.md**

`GET /api/me/settings` 行的说明改为「我的个人设置（深合并，含绑定邮箱 `email`）」，其 `PUT` 行说明改「更新个人设置（深合并；email 仅经邮箱验证接口变更）」，然后 `/api/me/settings` 的 `PUT` 行后插入：

```markdown
| `POST` | `/api/me/email/code` | 必须 | 发送邮箱验证码（bind/unbind，60s 冷却；mail 未配置 503） |
| `POST` | `/api/me/email/bind` | 必须 | 绑定/换绑邮箱（验证码校验） |
| `POST` | `/api/me/email/unbind` | 必须 | 解绑邮箱（当前邮箱验证码确认） |
```

- [ ] **Step 4: 全量回归**

Run: `python -m pytest`
Expected: 全部 passed（`test_llm.py` 默认排除）

- [ ] **Step 5: squash + 唯一 commit**

```bash
git reset --soft <BASE>   # BASE = 本任务起点 commit（执行时由控制器提供）
git add webapp/profile/email_service.py webapp/profile/app.py \
  webapp/static/settings.js webapp/static/settings.html core/web/static/profile.css \
  test/test_email_code_service.py test/scripts/check_profile_email_bind.py \
  CHANGELOG.md core/config.py specs/web-gallery.md
git commit -m "feat(个人中心): 邮箱绑定（验证码绑定/换绑/解绑）"
```

（绝不 `git add -A`；工作区 3 个既有 untracked `docs/superpowers/plans/2026-08-31-*.md` 不得入库。）

- [ ] **Step 6: 验证收尾**

Run: `git log --oneline <BASE>..HEAD`（应恰好 1 个 commit）；`git status --short`（应仅 3 个既有 untracked）
