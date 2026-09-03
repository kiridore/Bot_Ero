"""日程日历 API 行为测试：鉴权、month 校验、展开下发、隐私边界。

独立进程运行: python test/scripts/check_alarm_calendar_api.py
（pytest 由 test/test_webapp_api_suites.py 子进程纳入统一回归）
"""

import os
import sqlite3
import tempfile

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_cal_test_")
_db = os.path.join(_tmp, "test.db")
from _env import write_config  # 同目录 helper：生成临时 config.yaml

os.environ["BOTERO_CONFIG"] = write_config(_tmp, paths={"db": _db})

_conn = sqlite3.connect(_db)
_cur = _conn.cursor()
from core.database_manager import init_schema  # noqa: E402
init_schema(_conn, _cur)
_conn.commit()
_conn.close()

from datetime import datetime, timedelta  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from core.auth import make_login_key  # noqa: E402
from core.database_manager import DbManager  # noqa: E402
from webapp.app import app  # noqa: E402

client = TestClient(app)
DB = DbManager()  # 模块级强引用：避免临时 DbManager() 被共享连接关闭
ME, OTHER = "111", "222"
H = {"Authorization": "Bearer " + make_login_key(ME)}
JH = {"Content-Type": "application/json", **H}
OH = {"Authorization": "Bearer " + make_login_key(OTHER)}

import webapp.alarms.alarm_service as svc  # noqa: E402
svc.resolve_display_name = lambda uid: "用户" + str(uid)


def check(name, ok, extra=""):
    global fail
    print(f"{'ok' if ok else 'FAIL'} - {name}" + (f" {extra}" if extra else ""))
    if not ok:
        fail += 1


fail = 0
NEXT_MONTH = (datetime.now().replace(day=1) + timedelta(days=32)).replace(day=1)
MKEY = NEXT_MONTH.strftime("%Y-%m")
FIRE = NEXT_MONTH.replace(day=10, hour=8, minute=0)

# —— 鉴权与参数校验 ——
r = client.get(f"/api/me/calendar?month={MKEY}")
check("未登录 401", r.status_code == 401)
r = client.get("/api/me/calendar?month=2026-13", headers=H)
check("month 非法 400", r.status_code == 400, r.text)
r = client.get("/api/me/calendar?month=2026-9", headers=H)
check("month 非两位 400", r.status_code == 400)

# —— 展开下发与隐私 ——
DB.alarm.add(int(ME), FIRE, "我的群闹钟", group_id=123, is_private=False)
DB.alarm.add(int(OTHER), FIRE.replace(hour=9), "别人的群闹钟", group_id=123, is_private=False)
DB.alarm.add(int(OTHER), FIRE.replace(hour=10), "别人的私聊", group_id=None, is_private=True)
DB.alarm.add(int(ME), FIRE.replace(hour=11), "我的每天", recur=(1, 1, 0, 0))

r = client.get(f"/api/me/calendar?month={MKEY}", headers=H)
data = r.json()
key = FIRE.strftime("%Y-%m-%d")
names = [it["content"] for it in data["days"].get(key, [])]
check("日历 200 且含我的条目", r.status_code == 200 and "我的群闹钟" in names)
check("含别人的群闹钟且非本人标记", "别人的群闹钟" in names and any(
    it["content"] == "别人的群闹钟" and not it["is_mine"] and it["scope"] == "group"
    for it in data["days"][key]))
check("他人私聊闹钟不下发", "别人的私聊" not in names)
check("循环闹钟同日展开", "我的每天" in names)
next_key = (FIRE + timedelta(days=1)).strftime("%Y-%m-%d")
check("循环闹钟次日展开", next_key in data["days"])
check("同日按时间排序", [it["time"] for it in data["days"][key]]
      == sorted(it["time"] for it in data["days"][key]))

# —— scope 与编辑（Task 2）——
tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

r = client.post("/api/me/alarms", headers=JH, json={
    "content": "网页群闹钟", "schedule_type": "once_date", "date": tomorrow, "time": "21:00",
    "scope": "group",
})
gid_new = r.json().get("id")
db_cur = DB.cur
db_cur.execute("SELECT is_private, group_id FROM group_alarms WHERE id = ?", (gid_new,))
is_priv, gid_val = db_cur.fetchone()
check("POST scope=group 写群字段", r.status_code == 200 and int(is_priv) == 0
      and int(gid_val) == 296470819, r.text)

r = client.post("/api/me/alarms", headers=JH, json={
    "content": "网页私聊闹钟", "schedule_type": "once_date", "date": tomorrow, "time": "21:30",
})
priv_new = r.json().get("id")
db_cur.execute("SELECT is_private FROM group_alarms WHERE id = ?", (priv_new,))
check("POST 默认 private", int(db_cur.fetchone()[0]) == 1)

r = client.put(f"/api/me/alarms/{gid_new}", headers=JH, json={
    "content": "改成每天群提醒", "schedule_type": "daily", "time": "08:05", "scope": "group",
})
check("PUT 200", r.status_code == 200 and r.json().get("id") == gid_new, r.text)
db_cur.execute("SELECT content, recur_kind, recur_a FROM group_alarms WHERE id = ?", (gid_new,))
content_v, rk_v, ra_v = db_cur.fetchone()
check("PUT 重算规则", content_v == "改成每天群提醒" and int(rk_v) == 1 and int(ra_v) == 1)

r = client.put(f"/api/me/alarms/{gid_new}", headers={"Content-Type": "application/json", **OH},
               json={"content": "抢改", "schedule_type": "daily", "time": "01:00"})
check("PUT 非创建者 400", r.status_code == 400)

r = client.put(f"/api/me/alarms/{gid_new}", headers=JH, json={
    "content": "转私聊", "schedule_type": "daily", "time": "08:05", "scope": "private",
})
db_cur.execute("SELECT is_private, group_id FROM group_alarms WHERE id = ?", (gid_new,))
is_priv2, gid2 = db_cur.fetchone()
check("PUT 群转私聊字段翻转", int(is_priv2) == 1 and int(gid2) == 0)

# —— 路由与页面（Task 4）——
r = client.get("/alarms", headers=H, follow_redirects=False)
check("旧 /alarms 302（登录态）", r.status_code == 302 and r.headers.get("location") == "/profile/schedule")
r = client.get("/profile/schedule", follow_redirects=False)
check("未登录页面 302 登录", r.status_code == 302 and "/login" in r.headers.get("location", ""))
r = client.get("/profile/schedule", headers=H)
check("日程页 200", r.status_code == 200 and "日程" in r.text)
r = client.get("/entries.json", headers=H)
check("静态资产 no-cache 重验证", r.headers.get("cache-control") == "no-cache"
      and client.get("/shared/nav.js", headers=H).headers.get("cache-control") == "no-cache")
fr = client.get("/favicon.ico")
check("favicon 免登录可取", fr.status_code == 200 and fr.headers.get("content-type") == "image/png")
check("导航数据已是日程", "\u65e5\u7a0b" in r.text and "/profile/schedule" in r.text)

print(f"\n{'全部通过' if fail == 0 else f'{fail} 项失败'}")
sys.exit(1 if fail else 0)
