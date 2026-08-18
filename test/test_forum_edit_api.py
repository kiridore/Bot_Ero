"""议事厅编辑/删除 API 行为测试：作者权限、字段更新、时间线事件撤回+重发。

使用临时 DB（全新 schema，不触碰 data.db），真实登录密钥走完整鉴权链路；
时间线 emit/retract 打桩记录调用。运行：python test/test_forum_edit_api.py
"""

import os
import sqlite3
import tempfile
from unittest.mock import patch

# 必须在 import core.config / webapp 之前重定向 DB
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_forum_test_")
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


BODY = '{"type":"doc","content":[{"type":"paragraph","content":[{"type":"text","text":"正文一"}]}]}'

with patch("webapp.forum.app.emit_event") as m_emit, patch("webapp.forum.app.retract_event") as m_retract:
    # —— 创建 ——
    r = client.post("/api/forum/posts", headers=AH, json={
        "type": "post", "title": "测试帖", "body_json": BODY, "tags": ["测试"],
    })
    check("创建帖子 200", r.status_code == 200, r.text)
    pid = r.json().get("id")
    check("返回 id", isinstance(pid, int))
    check("创建时发时间线事件（forum_post:{id}）",
          m_emit.call_count == 1 and m_emit.call_args.kwargs.get("source") == "forum"
          and m_emit.call_args.kwargs.get("dedup_key") == f"forum_post:{pid}")

    # —— 权限：他人编辑 403 ——
    r = client.patch(f"/api/forum/posts/{pid}", headers=BH, json={"title": "篡改"})
    check("他人编辑 403", r.status_code == 403, r.text)
    check("403 后未触发事件", m_emit.call_count == 1)

    # —— 作者编辑 ——
    import time
    time.sleep(1.1)  # 秒级时间戳：跨秒后再编辑，updated_at 断言才有效
    r = client.patch(f"/api/forum/posts/{pid}", headers=AH, json={
        "title": "测试帖改", "body_json": '{"type":"doc"}', "tags": ["测试2", "新tag"],
    })
    check("作者编辑 200", r.status_code == 200, r.text)
    check("编辑后撤回旧事件", m_retract.call_count == 1
          and m_retract.call_args.kwargs.get("source") == "forum"
          and m_retract.call_args.kwargs.get("dedup_key") == f"forum_post:{pid}")
    check("编辑后按同 key 重发（重新入列按新事件计算未读）",
          m_emit.call_count == 2 and m_emit.call_args.kwargs.get("dedup_key") == f"forum_post:{pid}")

    g = client.get(f"/api/forum/posts/{pid}", headers=AH)
    post = g.json()
    check("GET 显示新标题", post.get("title") == "测试帖改")
    check("GET 显示新 tags", sorted(post.get("tags", [])) == ["新tag", "测试2"])
    check("GET 显示新正文", post.get("body_json") == '{"type":"doc"}')
    check("updated_at 已刷新", post.get("updated_at") != post.get("created_at"))

    # —— tags 清空 ——
    r = client.patch(f"/api/forum/posts/{pid}", headers=AH, json={"tags": []})
    check("tags 清空 200", r.status_code == 200, r.text)
    check("GET tags 为空", client.get(f"/api/forum/posts/{pid}", headers=AH).json().get("tags") == [])
    tg = client.get("/api/forum/tags", headers=AH).json()["tags"]
    check("编辑移除的 tag 已从列表消失", not any(t["name"] in ("测试", "测试2", "新tag") for t in tg))

    # —— 独立创建的无引用 tag 不展示（引用 0 隐藏） ——
    r = client.post("/api/forum/tags", headers=AH, json={"name": "孤悬"})
    check("独立创建 tag 200", r.status_code == 200, r.text)
    tg = client.get("/api/forum/tags", headers=AH).json()["tags"]
    check("无引用 tag 不展示", not any(t["name"] == "孤悬" for t in tg))

    # —— 不存在 404 ——
    r = client.patch("/api/forum/posts/999999", headers=AH, json={"title": "x"})
    check("编辑不存在帖子 404", r.status_code == 404, r.text)

    # —— 投票：编辑标题不影响子投票结构 ——
    r = client.post("/api/forum/posts", headers=AH, json={
        "type": "poll", "title": "周末做什么",
        "polls": [{"title": "问题", "allow_multi": False,
                   "options": [{"text": "选项A"}, {"text": "选项B"}]}],
    })
    p_pid = r.json()["id"]
    r = client.patch(f"/api/forum/posts/{p_pid}", headers=AH, json={"title": "周末做什么改"})
    check("投票改标题 200", r.status_code == 200, r.text)
    gp = client.get(f"/api/forum/posts/{p_pid}", headers=AH).json()
    check("投票选项保持不变",
          [o["text"] for p in gp.get("polls", []) for o in p["options"]] == ["选项A", "选项B"])

    # —— 评论级联删除 ——
    r = client.post(f"/api/forum/posts/{pid}/comments", headers=BH, json={"body_text": "楼下评论"})
    check("他人可评论 200", r.status_code == 200, r.text)

    # —— 权限：删除他人帖子 403 ——
    r2 = client.post("/api/forum/posts", headers=BH, json={"type": "post", "title": "B的帖子"})
    b_pid = r2.json()["id"]
    r = client.delete(f"/api/forum/posts/{b_pid}", headers=AH)
    check("删除他人帖子 403", r.status_code == 403, r.text)

    # —— 删帖清理悬空 tag ——
    r = client.post("/api/forum/posts", headers=AH, json={"type": "post", "title": "带tag帖", "body_json": "", "tags": ["悬空待删"]})
    t_pid = r.json()["id"]
    tg = client.get("/api/forum/tags", headers=AH).json()["tags"]
    check("引用中的 tag 正常展示（count=1）", any(t["name"] == "悬空待删" and t["post_count"] == 1 for t in tg))
    r = client.delete(f"/api/forum/posts/{t_pid}", headers=AH)
    check("删除带 tag 帖 200", r.status_code == 200, r.text)
    tg = client.get("/api/forum/tags", headers=AH).json()["tags"]
    check("删帖后悬空 tag 不再展示", not any(t["name"] == "悬空待删" for t in tg))
    _c = sqlite3.connect(_db)
    ntag = _c.execute("SELECT COUNT(*) FROM forum_tags WHERE name = '悬空待删'").fetchone()[0]
    _c.close()
    check("悬空 tag 已从 forum_tags 物理删除", ntag == 0)

    # —— 作者删除：级联 + 时间线撤回 ——
    r = client.delete(f"/api/forum/posts/{pid}", headers=AH)
    check("作者删除 200", r.status_code == 200, r.text)
    check("删除后撤回事件", m_retract.call_count >= 2
          and m_retract.call_args.kwargs.get("dedup_key") == f"forum_post:{pid}")
    check("删除后 GET 404", client.get(f"/api/forum/posts/{pid}", headers=AH).status_code == 404)
    _c = sqlite3.connect(_db)
    n = _c.execute("SELECT COUNT(*) FROM forum_comments WHERE post_id = ?", (pid,)).fetchone()[0]
    nv = _c.execute("SELECT COUNT(*) FROM forum_post_tags WHERE post_id = ?", (pid,)).fetchone()[0]
    _c.close()
    check("评论级联删除", n == 0)
    check("tag 关联级联删除", nv == 0)

print()
print("PASS" if fail == 0 else f"{fail} FAILURES")
raise SystemExit(1 if fail else 0)
