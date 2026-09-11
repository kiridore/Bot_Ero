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
email_service._pending.clear()
r = client.post("/api/me/email/code", headers=MH, json={"email": "x@x.com", "purpose": "unbind"})
check("未绑定时 unbind 发码 400", r.status_code == 400 and "未绑定" in r.json()["detail"], r.text)

# --- 未登录 401 / purpose 非法 400 ---
r = client.post("/api/me/email/code", json={"email": "a@b.com", "purpose": "bind"})
check("未登录 401", r.status_code == 401, str(r.status_code))
r = client.post("/api/me/email/code", headers=MH, json={"email": "a@b.com", "purpose": "hack"})
check("purpose 非法 400", r.status_code == 400, r.text)

print(f"\n{'PASS' if fail == 0 else 'FAIL'}: {fail} failures")
sys.exit(0 if fail == 0 else 1)
