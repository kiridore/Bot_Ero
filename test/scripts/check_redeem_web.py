"""个人主页兑换码 API 回归：原子兑换、失败回滚、历史兼容与登录门控。

独立进程运行: python test/scripts/check_redeem_web.py
（pytest 由 test/test_webapp_api_suites.py 子进程自动纳入统一回归）
"""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_redeem_web_")
_db = os.path.join(_tmp, "test.db")
sys.path.insert(0, str(PROJECT_ROOT / "test" / "scripts"))
from _env import write_config  # noqa: E402

os.environ["BOTERO_CONFIG"] = write_config(
    _tmp,
    paths={"db": _db, "images": os.path.join(_tmp, "record_images")},
    thumbs={"cache_dir": os.path.join(_tmp, "thumb_cache")},
)

from core import config  # noqa: E402
from core import context  # noqa: E402
from core.database_manager import init_schema  # noqa: E402

_conn = sqlite3.connect(_db)
init_schema(_conn, _conn.cursor())
# 迁移前历史数据：本人旧兑换记录（码已不在注册表 → 显示占位说明）
_conn.execute(
    "INSERT INTO redeem_code_usage (user_id, code, used_at) VALUES (12345601, 'OLD1-CODE-0001', '2026-01-01 08:00:00')"
)
_conn.commit()

from fastapi.testclient import TestClient  # noqa: E402
from core.auth import make_login_key  # noqa: E402
from webapp.app import app  # noqa: E402
from webapp.profile import redeem_service  # noqa: E402

ME = "12345601"
OTHER = "12345602"
MH = {"Authorization": "Bearer " + make_login_key(int(ME))}
OH = {"Authorization": "Bearer " + make_login_key(int(OTHER))}
client = TestClient(app)
fail = 0


def check(name, ok, extra=""):
    global fail
    print(f"{'ok' if ok else 'FAIL'} - {name}" + (f" {extra}" if extra else ""))
    if not ok:
        fail += 1


def usage_rows(uid=int(ME)):
    conn = sqlite3.connect(_db)
    rows = conn.execute(
        "SELECT code FROM redeem_code_usage WHERE user_id = ? ORDER BY code", (uid,)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def has_title(uid, tid):
    conn = sqlite3.connect(_db)
    row = conn.execute(
        "SELECT 1 FROM user_titles WHERE user_id = ? AND title_id = ?", (str(uid), tid)
    ).fetchone()
    conn.close()
    return row is not None


def points_of(uid):
    conn = sqlite3.connect(_db)
    row = conn.execute("SELECT points FROM user_assets WHERE user_id = ?", (str(uid),)).fetchone()
    conn.close()
    return int(row[0]) if row else 0


# —— 登录门控：未携带凭证一律 401，不执行业务 ——
r = client.get("/api/me/redeem/history")
check("未登录历史 401", r.status_code == 401)
r = client.post("/api/me/redeem", json={"code": "TEST-CODE-TEST"})
check("未登录兑换 401", r.status_code == 401)
check("未登录不写库", usage_rows() == ["OLD1-CODE-0001"])

# —— 格式与未知码：拒绝且不写库 ——
r = client.post("/api/me/redeem", json={"code": "abc"}, headers=MH)
check("格式错误 400", r.status_code == 400 and "格式" in r.json()["detail"])
r = client.post("/api/me/redeem", json={"code": "XXXX-XXXX-XXXX"}, headers=MH)
check("未知码 400", r.status_code == 400 and "不存在" in r.json()["detail"])
check("拒绝路径不写库", usage_rows() == ["OLD1-CODE-0001"])

# —— 有效兑换（小写输入归一）＋ 重复拒绝 ——
r = client.post("/api/me/redeem", json={"code": "test-code-test"}, headers=MH)
check("小写输入兑换成功", r.status_code == 200 and "测试员" in r.json()["message"])
check("称号 501 已解锁", has_title(ME, 501))
r2 = client.post("/api/me/redeem", json={"code": "TEST-CODE-TEST"}, headers=MH)
check("重复兑换 400", r2.status_code == 400 and "已使用" in r2.json()["detail"])

# —— 组合奖励：称号 + 积分 ——
conn = sqlite3.connect(_db)
conn.execute("INSERT OR IGNORE INTO user_assets (user_id, points) VALUES (?, 0)", (str(ME),))
conn.commit()
conn.close()
r = client.post("/api/me/redeem", json={"code": "ONLY-YEAR-ONCE"}, headers=MH)
check("周年码成功且积分+10", r.status_code == 200 and points_of(ME) == 10 and has_title(ME, 502))

# —— 历史：含迁移前旧行、已下架码占位说明、倒序、仅本人 ——
r = client.get("/api/me/redeem/history", headers=MH)
items = r.json()["items"]
codes = [it["code"] for it in items]
check("历史含旧记录", "OLD1-CODE-0001" in codes)
old_item = next(it for it in items if it["code"] == "OLD1-CODE-0001")
check("下架码显示占位说明", old_item["description"] == "（已下架）")
check("历史按时间倒序", codes.index("ONLY-YEAR-ONCE") < codes.index("OLD1-CODE-0001"))
r = client.get("/api/me/redeem/history", headers=OH)
check("他人历史隔离", r.status_code == 200 and r.json()["items"] == [])
r = client.post("/api/me/redeem", json={"code": "TEST-CODE-TEST"}, headers=OH)
check("另一用户可兑换同码（按用户一次性）", r.status_code == 200 and has_title(OTHER, 501))

# —— 回调失败：整体回滚（占位与已写奖励都消失），可立即重试 ——
state = {"boom": True}

def flaky(db, user_id):
    db.titles.unlock(user_id, 502, commit=False)  # 先写一个用户尚未拥有的称号
    if state["boom"]:
        raise RuntimeError("injected callback failure")

redeem_service.REDEEM_CODES["FAIL-TEST-CODE"] = {"description": "注入用", "callback": flaky}
r = client.post("/api/me/redeem", json={"code": "FAIL-TEST-CODE"}, headers=OH)
check("回调失败 500", r.status_code == 500 and "失败" in r.json()["detail"])
check("失败后占位回滚", "FAIL-TEST-CODE" not in usage_rows(int(OTHER)))
check("失败后奖励回滚", not has_title(OTHER, 502))
state["boom"] = False
r = client.post("/api/me/redeem", json={"code": "FAIL-TEST-CODE"}, headers=OH)
check("回滚后重试成功", r.status_code == 200 and usage_rows(int(OTHER)).count("FAIL-TEST-CODE") == 1)

print(f"\n{'全部通过' if fail == 0 else f'{fail} 项失败'}")
sys.exit(1 if fail else 0)
