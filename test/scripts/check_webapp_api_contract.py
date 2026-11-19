"""Webapp API 契约回归：OpenAPI 完整性、双形态分页、导航 API、直播流地址、统一认证、工具箱 tags。

独立进程运行: python test/scripts/check_webapp_api_contract.py
（pytest 由 test/test_webapp_api_suites.py 子进程自动纳入统一回归）
对应提案 2026-11-18-webapp-api-contract 的 AC01–AC04、AC07，
以及 2026-11-19-tools-tags-contract 的 AC01。
"""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_api_contract_")
_db = os.path.join(_tmp, "test.db")
sys.path.insert(0, str(PROJECT_ROOT / "test" / "scripts"))
from _env import write_config  # noqa: E402

os.environ["BOTERO_CONFIG"] = write_config(
    _tmp,
    paths={"db": _db, "images": os.path.join(_tmp, "record_images")},
    thumbs={"cache_dir": os.path.join(_tmp, "thumb_cache")},
)

from core.database_manager import init_schema  # noqa: E402

_conn = sqlite3.connect(_db)
init_schema(_conn, _conn.cursor())

from fastapi.testclient import TestClient  # noqa: E402
from core.auth import make_login_key  # noqa: E402
from webapp.app import app  # noqa: E402

ME = "12345601"
MH = {"Authorization": "Bearer " + make_login_key(int(ME))}
client = TestClient(app)
fail = 0


def check(name, ok, extra=""):
    global fail
    print(f"{'ok' if ok else 'FAIL'} - {name}" + (f" {extra}" if extra else ""))
    if not ok:
        fail += 1


# —— 打底数据：一个帖子（游标端点需要存在 post_id）——
r = client.post("/api/forum/posts", headers=MH, json={"type": "post", "title": "契约测试帖"})
check("建帖成功", r.status_code == 200, r.text[:120])
POST_ID = r.json().get("id")

# —— AC01 OpenAPI 完整性 ——
spec = client.get("/openapi.json", headers=MH)
check("openapi.json 登录可取", spec.status_code == 200)
doc = spec.json()

BINARY_API = {"/api/me/avatar.png", "/api/tools/icon"}  # 图片响应，非 JSON，契约豁免
_METHODS = ("get", "post", "put", "delete", "patch")
missing = []
for path, item in doc.get("paths", {}).items():
    if not path.startswith("/api/") or path in BINARY_API:
        continue
    for method, op in item.items():
        if method not in _METHODS:
            continue
        schemas = [
            resp.get("content", {}).get("application/json", {}).get("schema")
            for code, resp in op.get("responses", {}).items()
            if str(code).startswith("2")
        ]
        if not schemas or not any(schemas):
            missing.append(f"{method.upper()} {path}")
check("全部 /api/* JSON 路由有响应 schema", not missing, ", ".join(missing[:8]))

# —— AC02 分页（双形态）——
limit_params = [
    f"{m.upper()} {p}"
    for p, item in doc["paths"].items() if p.startswith("/api/")
    for m, op in item.items() if m in _METHODS
    for prm in op.get("parameters", []) if prm.get("name") == "limit"
]
check("全站无 limit 参数残留", not limit_params, ", ".join(limit_params))

for url in ("/api/guestbook", "/api/checkins", "/api/me/checkins"):
    r = client.get(url + "?page=1&page_size=5", headers=MH)
    body = r.json()
    check(f"偏移列表形态 {url}", r.status_code == 200
          and all(k in body for k in ("items", "total", "page", "page_size"))
          and body["page"] == 1)

r = client.get("/api/forum/posts?page_size=5", headers=MH)
body = r.json()
check("游标流形态 /api/forum/posts", r.status_code == 200
      and "items" in body and "next_cursor" in body)

r = client.get(f"/api/forum/posts/{POST_ID}/comments?page_size=5", headers=MH)
body = r.json()
check("游标流形态 comments（含 total）", r.status_code == 200
      and all(k in body for k in ("items", "next_cursor", "total")))

r = client.get("/api/timeline?page_size=5", headers=MH)
body = r.json()
check("时间线 events 形态", r.status_code == 200
      and all(k in body for k in ("events", "users", "next_cursor")))

r = client.get("/api/timeline/new?page_size=5", headers=MH)
body = r.json()
check("时间线增量 events 形态", r.status_code == 200
      and all(k in body for k in ("events", "users", "next_after")))

for bad in ("page=0", "page_size=0"):
    r = client.get(f"/api/guestbook?{bad}", headers=MH)
    check(f"非法分页 {bad} 422", r.status_code == 422 and "detail" in r.json())

# —— AC03 导航 API ——
r = client.get("/api/nav", headers=MH)
nav = r.json()
check("/api/nav 登录返回导航数组", r.status_code == 200 and isinstance(nav, list)
      and len(nav) > 0 and "name" in nav[0] and "desc" in nav[0])
r = client.get("/api/nav", follow_redirects=False)
check("/api/nav 未登录 401", r.status_code == 401 and "detail" in r.json())

# —— AC04 直播流地址 ——
import webapp.live.app as live_app  # noqa: E402

live_app.LIVE_HLS_URL = ""
r = client.get("/api/live/streams", headers=MH)
check("未配置 hls → null", r.status_code == 200 and r.json().get("hls") is None
      and bool(r.json().get("flv")))
live_app.LIVE_HLS_URL = "https://live.example/live.m3u8"
r = client.get("/api/live/streams", headers=MH)
check("配置 hls → 双地址", r.status_code == 200
      and r.json().get("hls") == "https://live.example/live.m3u8"
      and bool(r.json().get("flv")))

# —— AC07 统一认证 ——
schemes = (doc.get("components") or {}).get("securitySchemes") or {}
check("全局 bearerAuth scheme", schemes.get("bearerAuth", {}).get("scheme") == "bearer")
check("顶层全局 security", any("bearerAuth" in s for s in doc.get("security") or []))

exempt_ok = doc["paths"]["/api/auth/login"]["post"].get("security") == []
for p in ("/api/timeline/events", "/api/timeline/events/by-key", "/api/timeline/events/{event_id}"):
    for m, op in doc["paths"][p].items():
        if m in _METHODS and op.get("security") != []:
            exempt_ok = False
check("豁免路径标注 security: []", exempt_ok)

for url in ("/api/me/profile", "/api/guestbook", "/api/live/streams"):
    r = client.get(url, follow_redirects=False)
    check(f"无凭证 {url} 401", r.status_code == 401 and "detail" in r.json())
    r = client.get(url, headers=MH)
    check(f"带凭证 {url} 非 401", r.status_code != 401)

key = make_login_key(int(ME))
r = client.post("/api/auth/login", json={"key": key})
check("login 换取凭证", r.status_code == 200 and r.json().get("user_id") == ME
      and r.json().get("token"))

# —— 工具箱 tags 契约（2026-11-19-tools-tags-contract AC01）——
from core.database_manager import DbManager  # noqa: E402

db = DbManager()
TOOL_ID = db.tools.add_tool(ME, "契约测试链接", "标签回归", "https://example.com/tags", "example.com")
db.tools.add_link_tags(TOOL_ID, ["契约标签A", "契约标签B"], ME)
r = client.get("/api/tools?q=契约测试链接", headers=MH)
tool = next((it for it in r.json().get("items", []) if it.get("id") == TOOL_ID), None)
check("工具箱列表项含 tags 数组", r.status_code == 200 and tool is not None
      and tool.get("tags") == ["契约标签A", "契约标签B"], r.text[:200])
_conn2 = sqlite3.connect(_db)
rows = _conn2.execute(
    "SELECT t.name FROM tools_link_tags lt JOIN tools_tags t ON lt.tag_id = t.id "
    "WHERE lt.link_id = ? ORDER BY lt.tag_id", (TOOL_ID,)
).fetchall()
_conn2.close()
check("tags 与 tools_link_tags 一致", [row[0] for row in rows] == (tool or {}).get("tags"))
tool_schema = (doc.get("components") or {}).get("schemas", {}).get("ToolItemOut", {})
tags_schema = tool_schema.get("properties", {}).get("tags", {})
check("OpenAPI ToolItemOut 声明 tags 数组",
      tags_schema.get("type") == "array" and tags_schema.get("items", {}).get("type") == "string")

print(f"\n{'全部通过' if fail == 0 else f'{fail} 项失败'}")
sys.exit(1 if fail else 0)
