"""议事厅投票（单选/多选 + 多子投票）API 行为测试。

使用临时 DB（全新 schema，不触碰 data.db），真实登录密钥走完整鉴权链路；
时间线 emit 打桩记录调用。独立进程运行: python test/scripts/check_forum_poll.py（pytest 由 test/test_webapp_api_suites.py 子进程纳入统一回归）
"""

import os
import sqlite3
import tempfile
from unittest.mock import patch

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_forum_poll_test_")
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
from webapp.app import app  # noqa: E402

client = TestClient(app)
A = "Bearer " + make_login_key(1057613133)
B = "Bearer " + make_login_key(3915014383)
AH = {"Authorization": A, "Content-Type": "application/json"}
BH = {"Authorization": B, "Content-Type": "application/json"}

fail = 0


def check(name, ok, extra=""):
    global fail
    print(f"{'ok' if ok else 'FAIL'} - {name}" + (f" {extra}" if extra else ""))
    if not ok:
        fail += 1


with patch("webapp.forum.app.emit_event"):
    # —— 创建多子投票帖 ——
    r = client.post("/api/forum/posts", headers=AH, json={
        "type": "poll", "title": "周末团建",
        "polls": [
            {"title": "去哪？", "allow_multi": False,
             "options": [{"text": "爬山"}, {"text": "海边"}]},
            {"title": "吃什么？（多选）", "allow_multi": True,
             "options": [{"text": "烧烤"}, {"text": "火锅"}, {"text": "日料"}]},
        ],
    })
    check("创建多子投票帖 200", r.status_code == 200, r.text)
    pid = r.json()["id"]

    # —— 校验：无子投票 / 子投票少于 2 选项 ——
    r0 = client.post("/api/forum/posts", headers=AH, json={"type": "poll", "title": "空", "polls": []})
    check("无子投票被拒 400", r0.status_code == 400, r0.text)
    r0 = client.post("/api/forum/posts", headers=AH, json={
        "type": "poll", "title": "少选项",
        "polls": [{"title": "x", "allow_multi": False, "options": [{"text": "一个"}]}],
    })
    check("子投票少于 2 选项被拒 422", r0.status_code == 422, r0.text)

    # —— GET 结构 ——
    g = client.get(f"/api/forum/posts/{pid}", headers=AH).json()
    check("GET 返回 2 个子投票", len(g["polls"]) == 2)
    q1, q2 = g["polls"]
    check("子投票 1 为单选", q1["allow_multi"] is False and len(q1["options"]) == 2)
    check("子投票 2 为多选", q2["allow_multi"] is True and len(q2["options"]) == 3)
    check("初始无票", all(o["count"] == 0 for p in g["polls"] for o in p["options"]))
    check("初始未投", q1["my_vote"] == [] and q2["my_vote"] == [])

    opt_1a, opt_1b = [o["id"] for o in q1["options"]]
    opt_2a, opt_2b, opt_2c = [o["id"] for o in q2["options"]]

    # —— 单选 ——
    r = client.post(f"/api/forum/posts/{pid}/vote", headers=AH,
                    json={"poll_id": q1["id"], "option_ids": [opt_1a]})
    check("单选投票 200", r.status_code == 200, r.text)
    r = client.post(f"/api/forum/posts/{pid}/vote", headers=AH,
                    json={"poll_id": q1["id"], "option_ids": [opt_1b]})
    check("单选重复投（换选项）409", r.status_code == 409, r.text)
    r = client.post(f"/api/forum/posts/{pid}/vote", headers=AH,
                    json={"poll_id": q1["id"], "option_ids": [opt_1a, opt_1b]})
    check("单选投 2 选项被拒 400", r.status_code == 400, r.text)
    r = client.post(f"/api/forum/posts/{pid}/vote", headers=BH,
                    json={"poll_id": q1["id"], "option_ids": [opt_1b]})
    check("他人单选投票 200", r.status_code == 200, r.text)

    # —— 多选 ——
    r = client.post(f"/api/forum/posts/{pid}/vote", headers=AH,
                    json={"poll_id": q2["id"], "option_ids": [opt_2a]})
    check("多选投 1 项 200", r.status_code == 200, r.text)
    r = client.post(f"/api/forum/posts/{pid}/vote", headers=AH,
                    json={"poll_id": q2["id"], "option_ids": [opt_2a, opt_2b]})
    check("多选追加投 200", r.status_code == 200, r.text)
    r = client.post(f"/api/forum/posts/{pid}/vote", headers=AH,
                    json={"poll_id": q2["id"], "option_ids": [opt_2a]})
    check("多选重复投已投项 409", r.status_code == 409, r.text)

    # —— 票数与我的投票 ——
    g = client.get(f"/api/forum/posts/{pid}", headers=AH).json()
    q1, q2 = g["polls"]
    check("单选票数正确", [o["count"] for o in q1["options"]] == [1, 1])
    check("多选票数正确", [o["count"] for o in q2["options"]] == [1, 1, 0])
    check("我的单选投票", q1["my_vote"] == [opt_1a])
    check("我的多选投票", q2["my_vote"] == [opt_2a, opt_2b])

    # —— 无效选项 / 不存在的子投票 ——
    r = client.post(f"/api/forum/posts/{pid}/vote", headers=AH,
                    json={"poll_id": q1["id"], "option_ids": [opt_2a]})
    check("选项不属于该子投票 400", r.status_code == 400, r.text)
    r = client.post(f"/api/forum/posts/{pid}/vote", headers=AH,
                    json={"poll_id": 999999, "option_ids": [opt_1a]})
    check("不存在的子投票 404", r.status_code == 404, r.text)

    # —— 关闭后不可投 ——
    r = client.post(f"/api/forum/posts/{pid}/close", headers=AH)
    check("作者关闭投票 200", r.status_code == 200, r.text)
    r = client.post(f"/api/forum/posts/{pid}/vote", headers=BH,
                    json={"poll_id": q2["id"], "option_ids": [opt_2c]})
    check("关闭后投票 422", r.status_code == 422, r.text)

print()
print("PASS" if fail == 0 else f"{fail} FAILURES")
raise SystemExit(1 if fail else 0)
