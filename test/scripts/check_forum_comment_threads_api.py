"""议事厅评论线程 API 行为测试：两级嵌套回复、编辑、软删/硬删、时间线联动。

使用临时 DB（全新 schema，不触碰 data.db），真实登录密钥走完整鉴权链路；
时间线 emit/retract 打桩记录调用。独立进程运行: python test/scripts/check_forum_comment_threads_api.py（pytest 由 test/test_webapp_api_suites.py 子进程纳入统一回归）
"""

import os
import sqlite3
import tempfile
from unittest.mock import patch

# 必须在 import core.config / webapp 之前重定向 DB
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_forum_threads_test_")
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


def row(comment_id):
    c = sqlite3.connect(_db)
    r = c.execute(
        "SELECT id, post_id, author_user_id, body_text, status, parent_id, root_id, edited_at "
        "FROM forum_comments WHERE id = ?", (comment_id,),
    ).fetchone()
    c.close()
    return r


with patch("webapp.forum.app.emit_event") as m_emit, patch("webapp.forum.app.retract_event") as m_retract:
    r = client.post("/api/forum/posts", headers=AH, json={"type": "post", "title": "线程测试帖"})
    pid = r.json()["id"]
    r2 = client.post("/api/forum/posts", headers=AH, json={"type": "post", "title": "另一帖"})
    pid2 = r2.json()["id"]
    base_emit = m_emit.call_count  # 两个发帖事件

    # —— 嵌套创建：B 顶层 → A 回复 → B 回复回复 ——
    r = client.post(f"/api/forum/posts/{pid}/comments", headers=BH, json={"body_text": "顶层评论"})
    c1 = r.json()["id"]
    check("B 顶层评论 200", r.status_code == 200, r.text)
    r = client.post(f"/api/forum/posts/{pid}/comments", headers=AH,
                    json={"body_text": "一楼回复", "parent_id": c1})
    r1 = r.json()["id"]
    check("A 回复 c1 200", r.status_code == 200, r.text)
    check("r1.root_id = c1", row(r1)[6] == c1)
    check("每条评论各发一个时间线事件（forum_comment:{id}）",
          m_emit.call_count == base_emit + 2
          and m_emit.call_args.kwargs.get("dedup_key") == f"forum_comment:{r1}")

    r = client.post(f"/api/forum/posts/{pid}/comments", headers=BH,
                    json={"body_text": "回复的回复", "parent_id": r1})
    r2c = r.json()["id"]
    check("B 回复 r1 200", r.status_code == 200, r.text)
    check("r2.root_id 仍是顶层 c1（两级封顶）", row(r2c)[6] == c1 and row(r2c)[5] == r1)

    # —— 非法 parent ——
    r = client.post(f"/api/forum/posts/{pid}/comments", headers=AH,
                    json={"body_text": "x", "parent_id": 999999})
    check("parent 不存在 400", r.status_code == 400, r.text)
    r = client.post(f"/api/forum/posts/{pid2}/comments", headers=AH, json={"body_text": "他帖评论"})
    other = r.json()["id"]
    r = client.post(f"/api/forum/posts/{pid}/comments", headers=AH,
                    json={"body_text": "x", "parent_id": other})
    check("parent 跨帖 400", r.status_code == 400, r.text)

    # —— 线程列表结构 ——
    g = client.get(f"/api/forum/posts/{pid}/comments", headers=AH).json()
    check("total = 3", g.get("total") == 3)
    check("顶层只有 1 条线程", len(g["items"]) == 1)
    top = g["items"][0]
    check("顶层 id = c1", top["id"] == c1)
    check("回复串按时间正序", [x["id"] for x in top["replies"]] == [r1, r2c])
    rr = top["replies"][1]
    check("回复的回复标注 reply_to（指向 r1 作者 A）",
          rr.get("parent_id") == r1 and rr.get("reply_to_user_id") == "1057613133")
    check("直接回复顶层无 reply_to 字段", "reply_to_user_id" not in top["replies"][0])

    # —— 编辑：权限 + 时间线同 key 重发 ——
    r = client.patch(f"/api/forum/comments/{r1}", headers=BH, json={"body_text": "篡改"})
    check("他人编辑 403", r.status_code == 403, r.text)
    check("403 不触发事件", m_retract.call_count == 0)
    r = client.patch("/api/forum/comments/999999", headers=AH, json={"body_text": "x"})
    check("编辑不存在 404", r.status_code == 404, r.text)

    base_emit, base_retract = m_emit.call_count, m_retract.call_count
    r = client.patch(f"/api/forum/comments/{r1}", headers=AH, json={"body_text": "一楼回复（改）"})
    check("作者编辑 200", r.status_code == 200, r.text)
    check("返回 comment 含新正文", r.json()["comment"]["body_text"] == "一楼回复（改）")
    check("edited_at 已记录", row(r1)[7] is not None)
    check("编辑撤回旧事件", m_retract.call_count == base_retract + 1
          and m_retract.call_args.kwargs.get("dedup_key") == f"forum_comment:{r1}")
    check("编辑按同 key 重发", m_emit.call_count == base_emit + 1
          and m_emit.call_args.kwargs.get("dedup_key") == f"forum_comment:{r1}")
    g = client.get(f"/api/forum/posts/{pid}/comments", headers=AH).json()
    check("列表显示编辑后正文", g["items"][0]["replies"][0]["body_text"] == "一楼回复（改）")
    check("列表带 edited_at", g["items"][0]["replies"][0]["edited_at"] is not None)

    # —— 删除：叶子硬删 ——
    r = client.delete(f"/api/forum/comments/{r2c}", headers=AH)
    check("删除他人评论 403", r.status_code == 403, r.text)
    base_retract = m_retract.call_count
    r = client.delete(f"/api/forum/comments/{r2c}", headers=BH)
    check("作者删除叶子 200", r.status_code == 200, r.text)
    check("叶子已物理删除", row(r2c) is None)
    check("撤回叶子事件", m_retract.call_count == base_retract + 1
          and m_retract.call_args.kwargs.get("dedup_key") == f"forum_comment:{r2c}")
    g = client.get(f"/api/forum/posts/{pid}/comments", headers=AH).json()
    check("total 降为 2", g.get("total") == 2)

    # —— 删除：带回复的顶层软删占位 ——
    r = client.delete(f"/api/forum/comments/{c1}", headers=BH)
    check("删除带回复顶层 200", r.status_code == 200, r.text)
    rr = row(c1)
    check("顶层软删（status=deleted, body 清空）", rr[4] == "deleted" and rr[3] == "")
    g = client.get(f"/api/forum/posts/{pid}/comments", headers=AH).json()
    check("占位仍在线程列表", len(g["items"]) == 1 and g["items"][0]["id"] == c1
          and g["items"][0]["status"] == "deleted")
    check("回复链保留", [x["id"] for x in g["items"][0]["replies"]] == [r1])
    check("软删不进 total（total=1）", g.get("total") == 1)
    r = client.post(f"/api/forum/posts/{pid}/comments", headers=AH,
                    json={"body_text": "x", "parent_id": c1})
    check("回复软删占位 400", r.status_code == 400, r.text)

    # —— 最后一棵回复也删光 → 线程整体消失 ——
    r = client.delete(f"/api/forum/comments/{r1}", headers=AH)
    check("删除最后回复 200", r.status_code == 200, r.text)
    g = client.get(f"/api/forum/posts/{pid}/comments", headers=AH).json()
    check("无存活后代的占位不再返回", g["items"] == [] and g.get("total") == 0)

    # —— 回复软删占位（带回复的回复） ——
    r = client.post(f"/api/forum/posts/{pid2}/comments", headers=AH, json={"body_text": "他帖顶层"})
    t2 = r.json()["id"]
    r = client.post(f"/api/forum/posts/{pid2}/comments", headers=BH,
                    json={"body_text": "回复X", "parent_id": t2})
    x1 = r.json()["id"]
    r = client.post(f"/api/forum/posts/{pid2}/comments", headers=AH,
                    json={"body_text": "回复Y", "parent_id": x1})
    y1 = r.json()["id"]
    client.delete(f"/api/forum/comments/{x1}", headers=BH)
    g = client.get(f"/api/forum/posts/{pid2}/comments", headers=AH).json()
    replies = g["items"][0]["replies"]
    check("软删回复以占位形式留在串内",
          len(replies) == 2 and replies[0]["id"] == x1 and replies[0]["status"] == "deleted")
    check("占位后的回复可见", replies[1]["id"] == y1)

print()
print("PASS" if fail == 0 else f"{fail} FAILURES")
raise SystemExit(1 if fail else 0)
