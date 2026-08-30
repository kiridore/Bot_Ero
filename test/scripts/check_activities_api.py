"""活动创建/管理 API 行为测试：鉴权、owner 校验、创建校验、编辑白名单、B1 动作语义。

独立进程运行: python test/scripts/check_activities_api.py
（pytest 由 test/test_webapp_api_suites.py 子进程纳入统一回归）
"""

import os
import sqlite3
import tempfile

# 必须在 import core.config / webapp 之前重定向 DB
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_activity_test_")
_db = os.path.join(_tmp, "test.db")
os.environ["BOTERO_DB_PATH"] = _db

_conn = sqlite3.connect(_db)
_cur = _conn.cursor()
from core.database_manager import init_schema  # noqa: E402
init_schema(_conn, _cur)
_conn.commit()
_conn.close()

from fastapi.testclient import TestClient  # noqa: E402
from core.auth import make_login_key  # noqa: E402
from core.database_manager import DbManager  # noqa: E402
from webapp.app import app  # noqa: E402

client = TestClient(app)
DB = DbManager()  # 模块级强引用：避免临时 DbManager() 在链式取属性后被 __del__ 关闭共享连接
OWNER, OTHER, SUPER = "111", "222", "1057613133"
OH = {"Authorization": "Bearer " + make_login_key(OWNER), "Content-Type": "application/json"}
OTH = {"Authorization": "Bearer " + make_login_key(OTHER), "Content-Type": "application/json"}
SH = {"Authorization": "Bearer " + make_login_key(SUPER), "Content-Type": "application/json"}


def check(name, ok, extra=""):
    global fail
    print(f"{'ok' if ok else 'FAIL'} - {name}" + (f" {extra}" if extra else ""))
    if not ok:
        fail += 1


fail = 0

FUTURE = "2099-01-01 20:00"
FUTURE2 = "2099-02-01 20:00"

# —— 创建 ——
r = client.post("/api/activities", json={"type": "relay", "title": "接龙一"})
check("未登录创建 401", r.status_code == 401)
r = client.post("/api/activities", headers=OH, json={"type": "match", "title": "匹配一"})
check("匹配缺截止 400", r.status_code == 400, r.text)
r = client.post("/api/activities", headers=OH, json={
    "type": "relay", "title": "接龙一", "deadline": "2000-01-01 20:00"})
check("过去截止 400", r.status_code == 400, r.text)
r = client.post("/api/activities", headers=OH, json={"type": "relay", "title": "   "})
check("纯空白标题 400", r.status_code == 400, r.text)
r = client.post("/api/activities", headers=OH, json={
    "type": "relay", "title": "接龙一", "deadline": "not-a-date"})
check("截止格式错 400", r.status_code == 400, r.text)
r = client.post("/api/activities", headers=OH, json={
    "type": "match", "title": "匹配一", "deadline": FUTURE,
    "signup_deadline": FUTURE2, "description": "描述", "hours_per_user": 24})
check("匹配创建 200", r.status_code == 200, r.text)
mid = r.json().get("id")
check("返回 id 与公告", isinstance(mid, int) and "匹配下家" in r.json().get("announce", ""))
r = client.post("/api/activities", headers=OH, json={"type": "relay", "title": "接龙二"})
check("每群唯一进行中 409", r.status_code == 409, r.text)

# —— 公告查询 ——
r = client.get(f"/api/activities/{mid}/announce", headers=OTH)
check("非 owner 查公告 403", r.status_code == 403)
r = client.get(f"/api/activities/{mid}/announce", headers=OH)
check("owner 查公告 200", r.status_code == 200 and "活动发起" in r.json().get("announce", ""))

# —— 编辑 ——
r = client.patch(f"/api/activities/{mid}", headers=OTH, json={"title": "抢改"})
check("非 owner 编辑 403", r.status_code == 403)
r = client.patch(f"/api/activities/{mid}", headers=OH, json={
    "title": "匹配一改", "description": "新描述", "signup_deadline": FUTURE, "deadline": FUTURE2})
check("open 编辑 200", r.status_code == 200, r.text)
r = client.get(f"/api/activities/{mid}", headers=OH)
check("编辑生效", r.json().get("title") == "匹配一改" and r.json().get("description") == "新描述")
r = client.patch(f"/api/activities/{mid}", headers=OH, json={"hours_per_user": 0})
check("hours<=0 拒绝", r.status_code == 422, r.text)
r = client.patch(f"/api/activities/{mid}", headers=OH, json={"deadline": "2000-01-01 20:00"})
check("编辑过去截止 400", r.status_code == 400, r.text)
r = client.patch(f"/api/activities/{mid}", headers=OH, json={"title": "   "})
check("编辑空白标题 400", r.status_code == 400, r.text)
r = client.patch(f"/api/activities/{mid}", headers=OH, json={"nope": 1})
check("未知字段 422", r.status_code == 422, r.text)

# —— 取消后可再创建 ——
r = client.post(f"/api/activities/{mid}/cancel", headers=OH)
check("owner 取消 200", r.status_code == 200, r.text)
r = client.post(f"/api/activities/{mid}/cancel", headers=OH)
check("重复取消 409", r.status_code == 409)
r = client.post("/api/activities", headers=OH, json={
    "type": "relay", "title": "接龙二", "hours_per_user": 48,
    "signup_deadline": FUTURE, "deadline": FUTURE2})
check("取消后创建 200", r.status_code == 200, r.text)
rid = r.json()["id"]
check("接龙公告含限时", "每人限时 2 天" in r.json().get("announce", ""))
r = client.get("/api/activities", headers=OH)
check("列表含 created_by", any(a.get("created_by") == OWNER for a in r.json()["items"]))

# —— 开始（B1：signup_deadline=now）——
r = client.post(f"/api/activities/{rid}/start", headers=OTH)
check("非 owner 开始 403", r.status_code == 403)
r = client.post(f"/api/activities/{rid}/start", headers=OH)
check("接龙 0 人开始 409", r.status_code == 409, r.text)
DB.activity.add_member(rid, "333", "成员甲")
r = client.post(f"/api/activities/{rid}/start", headers=OH)
check("开始 200", r.status_code == 200, r.text)
r = client.get(f"/api/activities/{rid}", headers=OH)
check("signup_deadline 已置为当前", r.json().get("status") == "open"
      and r.json().get("signup_deadline", "9999") <= __import__("time").strftime("%Y-%m-%d %H:%M:%S"))
r = client.post(f"/api/activities/{rid}/start", headers=OH)
check("重复开始仍 open 200（幂等）", r.status_code == 200)

# 直接置 running 验证 running 态规则（心跳在测试进程不存在）
DB.activity.update_activity(rid, status="running")
r = client.patch(f"/api/activities/{rid}", headers=OH, json={"signup_deadline": FUTURE})
check("running 改报名截止 400", r.status_code == 400, r.text)
r = client.patch(f"/api/activities/{rid}", headers=OH, json={"hours_per_user": 72})
check("running 改限时 400", r.status_code == 400, r.text)
r = client.patch(f"/api/activities/{rid}", headers=OH, json={"title": "接龙二改", "deadline": FUTURE2})
check("running 改标题/截止 200", r.status_code == 200, r.text)
r = client.patch(f"/api/activities/{rid}", headers=SH, json={"title": "超管改"})
check("超管可编辑 200", r.status_code == 200, r.text)

# —— 提前结束（B1：deadline=now）——
r = client.post(f"/api/activities/{rid}/finish", headers=OTH)
check("非 owner 结束 403", r.status_code == 403)
r = client.post(f"/api/activities/{rid}/finish", headers=OH)
check("提前结束 200", r.status_code == 200, r.text)
r = client.get(f"/api/activities/{rid}", headers=OH)
check("deadline 已置为当前", r.json().get("deadline", "9999") <= __import__("time").strftime("%Y-%m-%d %H:%M:%S"))
DB.activity.update_activity(rid, status="finished")
r = client.patch(f"/api/activities/{rid}", headers=OH, json={"title": "x"})
check("finished 后编辑 409", r.status_code == 409)
r = client.post(f"/api/activities/{rid}/finish", headers=OH)
check("finished 后结束 409", r.status_code == 409)

# —— 匹配活动开始需 ≥2 人 ——
r = client.post("/api/activities", headers=OH, json={
    "type": "match", "title": "匹配二", "deadline": FUTURE})
mid2 = r.json()["id"]
DB.activity.add_member(mid2, "333", "成员甲")
r = client.post(f"/api/activities/{mid2}/start", headers=OH)
check("匹配 1 人开始 409", r.status_code == 409, r.text)
DB.activity.add_member(mid2, "444", "成员乙")
r = client.post(f"/api/activities/{mid2}/start", headers=OH)
check("匹配 2 人开始 200", r.status_code == 200, r.text)

# —— 404 ——
r = client.patch("/api/activities/99999", headers=OH, json={"title": "x"})
check("编辑不存在 404", r.status_code == 404)

# —— 页面路由（登录门控由 middleware 处理，Bearer 可过）——
r = client.get("/activities/new", headers=OH, follow_redirects=False)
check("发起页 200", r.status_code == 200 and "text/html" in r.headers.get("content-type", ""))
r = client.get("/activities/new", follow_redirects=False)
check("发起页未登录 302", r.status_code == 302)
r = client.get(f"/activities/{rid}/manage", headers=OH, follow_redirects=False)
check("管理页 200", r.status_code == 200 and "text/html" in r.headers.get("content-type", ""))
r = client.get("/activities/99999/manage", headers=OH)
check("管理页不存在 404", r.status_code == 404)

print(f"\n{'ALL PASS' if fail == 0 else f'{fail} FAILED'}")
sys.exit(1 if fail else 0)
