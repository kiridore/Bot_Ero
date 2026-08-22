"""时间线未读/已读状态 API 行为测试：首访基线、rowid 单调边界（同秒乱序）、
轮询/拉新分页、逐卡回执、追平推进水印、撤回联动（级联清理 + max 夹紧防回退）、
用户隔离、鉴权与旧页 keyset 回归。

独立进程运行: python test/scripts/check_timeline_unread.py（pytest 由 test/test_webapp_api_suites.py 子进程纳入统一回归）
"""
import os
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 必须在 import core.config / webapp 之前重定向 DB 与外部依赖
_tmp = tempfile.mkdtemp(prefix="botero_timeline_unread_test_")
_db = os.path.join(_tmp, "test.db")
os.environ["BOTERO_DB_PATH"] = _db
# 昵称解析立即失败降级（uid 直返），避免 192.168.x 超时拖慢测试
os.environ["BOTERO_ONEBOT_HTTP"] = "http://127.0.0.1:1"
os.environ["BOTERO_EVENT_TOKEN"] = "test-timeline-token"

_conn = sqlite3.connect(_db)
_cur = _conn.cursor()
from core.database_manager import init_schema  # noqa: E402
init_schema(_conn, _cur)
_conn.commit()

from fastapi.testclient import TestClient  # noqa: E402
from core.auth import make_login_key  # noqa: E402
from core.config import TIMELINE_TOKEN  # noqa: E402
from webapp.app import app  # noqa: E402

client = TestClient(app)
A = "Bearer " + make_login_key(1057613133)
B = "Bearer " + make_login_key(3915014383)
AH = {"Authorization": A, "Content-Type": "application/json"}
BH = {"Authorization": B, "Content-Type": "application/json"}
TH = {"Authorization": f"Bearer {TIMELINE_TOKEN}", "Content-Type": "application/json"}

fail = 0


def check(name, ok, extra=""):
    global fail
    print(f"{'ok' if ok else 'FAIL'} - {name}" + (f" {extra}" if extra else ""))
    if not ok:
        fail += 1


def insert_event(eid, received_at=None, title="测试事件", actor_qq="1057613133", dedup_key=None):
    """直接造数（确定 received_at；received_at 为空则用当前秒）。"""
    if received_at is None:
        received_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _conn.execute(
        "INSERT OR IGNORE INTO timeline_events"
        " (id, source, received_at, actor_id, actor_qq, target_type, target_url,"
        " title, description, data, dedup_key)"
        " VALUES (?, 'checkin', ?, ?, ?, NULL, NULL, ?, NULL, NULL, ?)",
        (eid, received_at, actor_qq, actor_qq, title, dedup_key),
    )
    _conn.commit()


def watermark_of(user_id):
    row = _conn.execute(
        "SELECT position FROM timeline_user_watermarks WHERE user_id = ?", (user_id,)
    ).fetchone()
    return int(row[0]) if row else None


def receipts_of(user_id):
    rows = _conn.execute(
        "SELECT event_id FROM timeline_read_events WHERE user_id = ?", (user_id,)
    ).fetchall()
    return sorted(r[0] for r in rows)


# —— A 首访空时间线：基线为 0（哨兵），后续首个事件判未读 ——
r = client.get("/api/timeline", headers=AH)
check("A 首访空时间线 200", r.status_code == 200, r.text)
data = r.json()
check("A 首访空事件", data["events"] == [] and data["next_cursor"] is None)
check("A 空时间线基线为 0", watermark_of("1057613133") == 0)

# —— 造历史事件（不同秒），A 空基线后视为新事件 ——
insert_event("checkin:old1", received_at="2026-08-18 09:00:00", dedup_key="k1")
insert_event("checkin:old2", received_at="2026-08-18 09:00:01", dedup_key="k2")
r = client.get("/api/timeline", headers=AH)
evs = r.json()["events"]
check("A 空基线后新事件未读", len(evs) == 2 and all(e["unread"] for e in evs))
check("事件响应含 seq 且新→旧", evs[0]["id"] == "checkin:old2" and evs[0]["seq"] > evs[1]["seq"])

# —— B 首访：已有历史全部视为已读，基线 = 最大 rowid ——
r = client.get("/api/timeline", headers=BH)
evs = r.json()["events"]
check("B 首访历史全部已读", len(evs) == 2 and not any(e["unread"] for e in evs))
check("B 基线为最大 rowid", watermark_of("3915014383") == 2)

# —— 同秒乱序：基线后插入同秒、id 字典序更小的事件，rowid 边界保证未读 ——
insert_event("checkin:aaa", received_at="2026-08-18 09:00:01", dedup_key="k3")
r = client.get("/api/timeline", headers=BH)
evs = r.json()["events"]
new_ev = [e for e in evs if e["id"] == "checkin:aaa"]
check("同秒更小 id 事件仍判未读", len(new_ev) == 1 and new_ev[0]["unread"] is True)

# —— poll 轻量计数 ——
r = client.get("/api/timeline/poll?after=2", headers=BH)
check("poll?after=2 计数 1", r.json()["count"] == 1, r.text)
r = client.get("/api/timeline/poll", headers=BH)
check("poll 无 after 用基线计数 1", r.json()["count"] == 1, r.text)

# —— 多页拉新（limit=1 循环，最老在前、无重复）——
insert_event("checkin:newer", received_at="2026-08-18 10:00:00", dedup_key="k4")
r = client.get("/api/timeline/new?after=2&limit=1", headers=BH)
d1 = r.json()
check("new 第一页取最老", len(d1["events"]) == 1 and d1["events"][0]["id"] == "checkin:aaa", r.text)
check("new 第一页 next_after 非空", d1["next_after"] is not None)
r = client.get(f"/api/timeline/new?after={d1['next_after']}&limit=1", headers=BH)
d2 = r.json()
check("new 第二页取较新", len(d2["events"]) == 1 and d2["events"][0]["id"] == "checkin:newer", r.text)
check("new 第二页 next_after 为 null", d2["next_after"] is None)
check("new 分页无重复", {d1["events"][0]["id"], d2["events"][0]["id"]} == {"checkin:aaa", "checkin:newer"})

# —— 只读最新：较旧新卡保持未读，水印不推进 ——
r = client.post("/api/timeline/read", headers=BH, json={"event_ids": ["checkin:newer"]})
check("read 返回 remaining 1", r.json()["remaining"] == 1, r.text)
r = client.get("/api/timeline", headers=BH)
evs = {e["id"]: e["unread"] for e in r.json()["events"]}
check("只读最新后该卡已读", evs.get("checkin:newer") is False)
check("较旧新卡仍未读", evs.get("checkin:aaa") is True)
check("部分读水印不推进", watermark_of("3915014383") == 2)

# —— 补读剩余：追平推进水印并清理回执 ——
r = client.post("/api/timeline/read", headers=BH, json={"event_ids": ["checkin:aaa"]})
check("补读后 remaining 0", r.json()["remaining"] == 0, r.text)
check("追平后水印推进到最大 rowid", watermark_of("3915014383") == 4)
check("追平后回执清理", receipts_of("3915014383") == [])

# —— 撤回联动：部分读后撤回最新，再补报不回退 ——
insert_event("checkin:e6", received_at="2026-08-18 11:00:00", dedup_key="k6")
insert_event("checkin:e7", received_at="2026-08-18 11:00:01", dedup_key="k7")
r = client.post("/api/timeline/read", headers=BH, json={"event_ids": ["checkin:e6"]})
check("读 e6 后 remaining 1", r.json()["remaining"] == 1, r.text)
r = client.delete("/api/timeline/events/checkin:e7", headers=TH)
check("撤回 e7", r.json().get("deleted") is True, r.text)
r = client.post("/api/timeline/read", headers=BH, json={"event_ids": ["checkin:e7"]})
check("撤回后补报 e7 remaining 0", r.json()["remaining"] == 0, r.text)
check("水印取 max 保持 5 不回退", watermark_of("3915014383") == 5)

# —— max 夹紧：水印已追平到最大事件后撤回该事件，再上报不得回退 ——
insert_event("checkin:e8", received_at="2026-08-18 12:00:00", dedup_key="k8")
r = client.post("/api/timeline/read", headers=BH, json={"event_ids": ["checkin:e8"]})
check("读 e8 追平 remaining 0", r.json()["remaining"] == 0, r.text)
check("水印推进到 6", watermark_of("3915014383") == 6)
r = client.delete("/api/timeline/events/checkin:e8", headers=TH)
check("撤回最大事件 e8", r.json().get("deleted") is True, r.text)
r = client.post("/api/timeline/read", headers=BH, json={"event_ids": ["checkin:old1"]})
check("再上报后水印仍 6 不回退", r.json()["remaining"] == 0 and watermark_of("3915014383") == 6, r.text)

# —— 幂等 / 未知 id / 回执级联清理 ——
r = client.post("/api/timeline/read", headers=BH, json={"event_ids": ["checkin:old1", "checkin:old1"]})
check("重复上报幂等", r.status_code == 200 and r.json()["remaining"] == 0, r.text)
r = client.post("/api/timeline/read", headers=BH, json={"event_ids": ["checkin:ghost"]})
check("未知 id 安全忽略", r.status_code == 200 and r.json()["remaining"] == 0, r.text)
insert_event("checkin:temp", received_at="2026-08-18 13:00:00", dedup_key="k9")
insert_event("checkin:temp2", received_at="2026-08-18 13:00:01", dedup_key="k10")
r = client.post("/api/timeline/read", headers=BH, json={"event_ids": ["checkin:temp"]})
check("temp 部分读 remaining 1", r.json()["remaining"] == 1, r.text)
check("temp 有回执", "checkin:temp" in receipts_of("3915014383"))
r = client.delete("/api/timeline/events/checkin:temp", headers=TH)
check("撤回 temp", r.json().get("deleted") is True, r.text)
check("撤回后回执级联清理", "checkin:temp" not in receipts_of("3915014383"))
r = client.post("/api/timeline/read", headers=BH, json={"event_ids": ["checkin:temp2"]})
check("读完 temp2 remaining 0", r.json()["remaining"] == 0, r.text)
max_rowid = _conn.execute("SELECT MAX(rowid) FROM timeline_events").fetchone()[0]
check("追平后水印等于最大 rowid", watermark_of("3915014383") == max_rowid)

# —— 用户隔离：A 基线 0，B 的读取不影响 A 的未读 ——
r = client.get("/api/timeline", headers=AH)
evs = r.json()["events"]
check("A 视角事件仍全部未读", len(evs) > 0 and all(e["unread"] for e in evs))

# —— 占位符回归：服务端保留原文，解析数据随 users 下发（客户端替换）——
insert_event("checkin:ph", received_at="2026-08-18 14:00:00", dedup_key="k11",
             title="{id:1057613133} 完成打卡")
r = client.get("/api/timeline", headers=BH, params={"limit": 1})
data = r.json()
ev = data["events"][0]
check("占位符原文保留", ev["title"] == "{id:1057613133} 完成打卡", ev["title"])
check("占位符解析数据随响应下发",
      data["users"].get("1057613133", {}).get("name") == "1057613133", str(data["users"]))

# —— 真实事件端点造数进入未读计数 ——
r = client.post("/api/timeline/events", headers=TH, json={
    "id": "checkin:via-api", "source": "checkin",
    "actor": {"id": "1057613133", "qq": "1057613133"},
    "display": {"title": "API 造数事件"},
    "dedup_key": "k12",
})
check("事件端点造数", r.status_code == 200 and r.json().get("inserted") is True, r.text)
r = client.get("/api/timeline", headers=BH, params={"limit": 5})
evs = {e["id"]: e["unread"] for e in r.json()["events"]}
check("端点事件进入未读计数", evs.get("checkin:via-api") is True, r.text)

# —— 鉴权与参数校验 ——
check("poll 未登录 401", client.get("/api/timeline/poll").status_code == 401)
check("new 未登录 401", client.get("/api/timeline/new").status_code == 401)
check("read 未登录 401", client.post("/api/timeline/read", json={"event_ids": ["x"]}).status_code == 401)
check("poll after 非法 422", client.get("/api/timeline/poll?after=abc", headers=BH).status_code == 422)
check("new limit 非法 422", client.get("/api/timeline/new?limit=0", headers=BH).status_code == 422)
check("read 空列表 422", client.post("/api/timeline/read", headers=BH, json={"event_ids": []}).status_code == 422)

# —— 旧页 keyset 分页与 next_cursor 回归 ——
r = client.get("/api/timeline", headers=BH,
               params={"cursor": "2026-08-18 10:00:00|checkin:newer", "limit": 1})
d = r.json()
check("向后 keyset 分页取 old2", len(d["events"]) == 1 and d["events"][0]["id"] == "checkin:old2", r.text)
check("next_cursor 正确", d["next_cursor"] == "2026-08-18 09:00:01|checkin:old2", d["next_cursor"])

_conn.close()
print()
print("PASS" if fail == 0 else f"{fail} FAILURES")
raise SystemExit(1 if fail else 0)
