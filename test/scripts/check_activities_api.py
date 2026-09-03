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
from _env import write_config  # 同目录 helper：生成临时 config.yaml

os.environ["BOTERO_CONFIG"] = write_config(
    _tmp, paths={"db": _db, "activity": os.path.join(_tmp, "activity_root")}
)

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

# —— 网页提交：me / submit / 隐私剥离 ——
import json as _json  # noqa: E402
import time as _time  # noqa: E402

H333 = {"Authorization": "Bearer " + make_login_key("333")}
H444 = {"Authorization": "Bearer " + make_login_key("444")}
DB.activity.update_activity(mid2, status="cancelled")  # 让出唯一进行中名额
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

r = client.post("/api/activities", headers=OH, json={
    "type": "relay", "title": "接龙三", "hours_per_user": 48, "deadline": FUTURE2})
rid3 = r.json()["id"]
DB.activity.add_member(rid3, "333", "成员甲")
DB.activity.add_member(rid3, "444", "成员乙")
DB.activity.set_ring(rid3, [("333", None, 1), ("444", None, 2)])
DB.activity.update_activity(rid3, status="running")
DB.activity.update_member(rid3, "333", received_at=_time.strftime("%Y-%m-%d %H:%M:%S"))

r = client.get(f"/api/activities/{rid3}/me", headers=H333)
check("me 当前棒可提交", r.status_code == 200 and r.json()["can_submit"] is True
      and r.json()["block_reason"] is None, r.text)
r = client.get(f"/api/activities/{rid3}/me", headers=H444)
check("me 非当前棒 not_my_turn", r.json()["block_reason"] == "not_my_turn")
r = client.get(f"/api/activities/{rid3}/me", headers=OH)
check("me 非成员 not_member", r.json()["member"] is None and r.json()["block_reason"] == "not_member")
r = client.get("/api/activities/99999/me", headers=OH)
check("me 不存在 404", r.status_code == 404)

r = client.post(f"/api/activities/{rid3}/submit", headers=H444, data={"content": "抢跑"})
check("submit 非轮到 409", r.status_code == 409 and "轮到你" in r.json().get("detail", ""), r.text)
r = client.post(f"/api/activities/{rid3}/submit", headers=H333, data={})
check("submit 空作品 400", r.status_code == 400, r.text)
r = client.post(f"/api/activities/{rid3}/submit", headers=H333,
                files=[("files", ("a.txt", b"hello", "text/plain"))], data={"content": "x"})
check("submit 非图片类型 400", r.status_code == 400, r.text)

r = client.post(f"/api/activities/{rid3}/submit", headers=H333,
                files=[("files", ("a.png", PNG, "image/png")),
                       ("files", ("b.png", PNG, "image/png"))],
                data={"content": "我的文字作品"})
check("submit 成功", r.status_code == 200 and r.json() == {"ok": True, "updated": False}, r.text)
from core.config import ACTIVITY_ROOT as _AR  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
check("图片落盘命名", (_Path(_AR) / str(rid3) / "imgs" / "1-1.png").is_file()
      and (_Path(_AR) / str(rid3) / "imgs" / "1-2.png").is_file())
m333 = DB.activity.get_member(rid3, "333")
check("提交写库", m333["status"] == "done" and m333["content"] == "我的文字作品"
      and _json.loads(m333["images"]) == ["1-1.png", "1-2.png"])

r = client.get(f"/api/activities/{rid3}", headers=H333)
img_row = next(m for m in r.json()["members"] if m["user_id"] == "333")
check("me 图片 URL 映射", img_row["images"] == [f"/archive/{rid3}/media/1-1.png", f"/archive/{rid3}/media/1-2.png"])

r = client.post(f"/api/activities/{rid3}/submit", headers=H333, data={"content": "改成纯文字"})
check("submit 更新覆盖", r.json() == {"ok": True, "updated": True}, r.text)
raw_imgs = DB.activity.get_member(rid3, "333")["images"]
check("更新后 images 清空", raw_imgs in (None, "[]"))  # 覆盖式：无图重传写 NULL（与 bot 一致）

r = client.get(f"/api/activities/{rid3}", headers=H333)
me_row = next(m for m in r.json()["members"] if m["user_id"] == "333")
other_row = next(m for m in r.json()["members"] if m["user_id"] == "444")
check("进行中他人作品剥离", other_row["content"] is None and other_row["images"] == []
      and other_row["submitted_at"] is None)
check("进行中本人保留", me_row["content"] == "改成纯文字")

DB.activity.update_member(rid3, "444", status="missed")
r = client.post(f"/api/activities/{rid3}/submit", headers=H444, data={"content": "补交"})
check("missed 提交 409", r.status_code == 409 and "截止" in r.json().get("detail", ""))
DB.activity.update_member(rid3, "444", status="pending")
DB.activity.update_activity(rid3, status="finished")
r = client.post(f"/api/activities/{rid3}/submit", headers=H444, data={"content": "x"})
check("finished 提交 409", r.status_code == 409)
r = client.get(f"/api/activities/{rid3}", headers=H444)
done_row = next(m for m in r.json()["members"] if m["user_id"] == "333")
check("finished 后归档公开", done_row["content"] == "改成纯文字"
      and done_row["images"] == [])  # 覆盖式更新已清图，归档跟随现状

DB.activity.update_activity(rid3, status="cancelled")  # 让位给匹配用例
r = client.post("/api/activities", headers=OH, json={
    "type": "match", "title": "匹配三", "deadline": FUTURE2})
mid3 = r.json()["id"]
DB.activity.add_member(mid3, "333", "成员甲")
DB.activity.add_member(mid3, "444", "成员乙")
DB.activity.set_ring(mid3, [("333", "444", 1), ("444", "333", 2)])
DB.activity.update_activity(mid3, status="running")
r = client.get(f"/api/activities/{mid3}/me", headers=H444)
check("match 无轮次限制", r.json()["can_submit"] is True, r.text)
r = client.post(f"/api/activities/{mid3}/submit", headers=H444,
                files=[("files", ("m.png", PNG, "image/png"))], data={"content": "任意时刻"})
check("match 提交 200", r.status_code == 200 and r.json()["updated"] is False, r.text)

# —— 归档媒体进行中鉴权 ——
r = client.get(f"/archive/{mid3}/media/2-1.png", headers=H444)
check("进行中本人可取媒体", r.status_code == 200)
r = client.get(f"/archive/{mid3}/media/2-1.png", headers=H333)
check("进行中他人成员 403", r.status_code == 403)
r = client.get(f"/archive/{mid3}/media/2-1.png", headers=OH)
check("进行中创建人可取", r.status_code == 200)
r = client.get(f"/archive/{mid3}/media/img_2_1.jpg", headers=H444)
check("bot 命名文件同样鉴权（不存在 404 而非 403）", r.status_code == 404)
r = client.get(f"/api/activities/{mid3}", headers=H333)
row444 = next(m for m in r.json()["members"] if m["user_id"] == "444")
check("match 他人已提交剥离", row444["content"] is None and row444["images"] == []
      and row444["submitted_at"] is None)
DB.activity.update_activity(mid3, status="finished")
r = client.get(f"/archive/{mid3}/media/2-1.png", headers=H333)
check("结束后成员可取归档", r.status_code == 200)

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
