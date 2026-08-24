"""议事厅浏览量 API 行为测试：详情 GET 计数、列表返回、404 不计数、旧库迁移补列。

使用临时 DB（全新 schema，不触碰 data.db），真实登录密钥走完整鉴权链路。
独立进程运行: python test/scripts/check_forum_views.py（pytest 由 test/test_webapp_api_suites.py 子进程纳入统一回归）
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

_tmp = tempfile.mkdtemp(prefix="botero_forum_views_")
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
AH = {
    "Authorization": "Bearer " + make_login_key(1057613133),
    "Content-Type": "application/json",
}

fail = 0


def check(name, ok, extra=""):
    global fail
    print(f"{'ok' if ok else 'FAIL'} - {name}" + (f" {extra}" if extra else ""))
    if not ok:
        fail += 1


# —— 建帖（创建不计浏览） ——
with patch("webapp.forum.app.emit_event"), patch("webapp.forum.app.retract_event"):
    r = client.post("/api/forum/posts", headers=AH, json={
        "type": "post", "title": "浏览量测试帖",
        "body_json": '{"type":"doc","content":[{"type":"paragraph","content":[{"type":"text","text":"正文"}]}]}',
    })
    check("创建帖子 200", r.status_code == 200, r.text)
    pid = r.json()["id"]

_c = sqlite3.connect(_db)
check("新建帖 view_count 初始为 0", _c.execute(
    "SELECT view_count FROM forum_posts WHERE id = ?", (pid,)).fetchone()[0] == 0)
_c.close()

# —— 详情 GET 计数：每次 +1，返回值含本次浏览 ——
g = client.get(f"/api/forum/posts/{pid}", headers=AH)
check("首次详情 GET 200", g.status_code == 200)
check("首次 GET view_count=1（含本次浏览）", g.json().get("view_count") == 1, str(g.json().get("view_count")))

client.get(f"/api/forum/posts/{pid}", headers=AH)
g = client.get(f"/api/forum/posts/{pid}", headers=AH)
check("第三次 GET view_count=3", g.json().get("view_count") == 3, str(g.json().get("view_count")))

# 另一个登录用户浏览同样 +1（按 GET 次数计，不按人去重）
BH = {"Authorization": "Bearer " + make_login_key(3915014383)}
g = client.get(f"/api/forum/posts/{pid}", headers=BH)
check("他人 GET 也计数（view_count=4）", g.json().get("view_count") == 4, str(g.json().get("view_count")))

# —— 列表返回 view_count ——
lst = client.get("/api/forum/posts", headers=AH).json()
item = next((it for it in lst.get("items", []) if it["id"] == pid), None)
check("列表项含 view_count=4", item is not None and item.get("view_count") == 4,
      str(item and item.get("view_count")))

# —— 不存在 404（不崩、不计数） ——
r = client.get("/api/forum/posts/999999", headers=AH)
check("不存在帖子详情 404", r.status_code == 404, r.text)

# —— 删除后 404（软意义上已删帖不计数） ——
with patch("webapp.forum.app.emit_event"), patch("webapp.forum.app.retract_event"):
    r = client.post("/api/forum/posts", headers=AH, json={"type": "post", "title": "待删帖"})
    del_pid = r.json()["id"]
    r = client.delete(f"/api/forum/posts/{del_pid}", headers=AH)
    check("删除帖子 200", r.status_code == 200, r.text)
    check("删帖后详情 GET 404", client.get(f"/api/forum/posts/{del_pid}", headers=AH).status_code == 404)

# —— 旧库迁移：无 view_count 列的 forum_posts 补列，存量行回填 0 ——
old_db = os.path.join(_tmp, "old.db")
oc = sqlite3.connect(old_db)
oc.execute("""
    CREATE TABLE forum_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        author_user_id TEXT NOT NULL,
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        body_json TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'open',
        pinned INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        notified_at TEXT,
        poll_anonymous INTEGER NOT NULL DEFAULT 0,
        poll_deadline TEXT
    );
""")
oc.execute(
    "INSERT INTO forum_posts (author_user_id, type, title, created_at, updated_at) "
    "VALUES ('1057613133', 'post', '旧库帖', '2026-01-01 00:00:00', '2026-01-01 00:00:00')")
oc.commit()
init_schema(oc, oc.cursor())  # 迁移幂等：缺列则 ALTER 补列
cols = [row[1] for row in oc.execute("PRAGMA table_info(forum_posts)").fetchall()]
check("旧库 init_schema 后补 view_count 列", "view_count" in cols, str(cols))
row = oc.execute("SELECT view_count FROM forum_posts WHERE title = '旧库帖'").fetchone()
check("存量行回填 0", row and row[0] == 0, str(row))
init_schema(oc, oc.cursor())  # 再跑一次不炸（幂等）
row = oc.execute("SELECT view_count FROM forum_posts WHERE title = '旧库帖'").fetchone()
check("迁移幂等（重复 init_schema 值不变）", row and row[0] == 0)
oc.close()

print()
print("PASS" if fail == 0 else f"{fail} FAILURES")
raise SystemExit(1 if fail else 0)
