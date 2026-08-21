"""全站登录门控行为测试：未登录 302/401、cookie 与 Bearer 双通道、白名单放行。

使用临时 DB（全新 schema，不触碰 data.db）；OneBot 昵称/头像解析打桩避免真实网络。
运行：python test/test_web_auth_guard.py
"""

import os
import sqlite3
import tempfile
import uuid
from unittest.mock import patch

# 必须在 import core.config / webapp 之前重定向 DB
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_guard_test_")
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
from core.config import TIMELINE_TOKEN  # noqa: E402
from webapp.app import app  # noqa: E402

client = TestClient(app)
KEY = make_login_key(1057613133)
COOKIE = {"botero_key": KEY}
AUTH = {"Authorization": f"Bearer {KEY}"}

fail = 0


def check(name, ok, extra=""):
    global fail
    print(f"{'ok' if ok else 'FAIL'} - {name}" + (f" {extra}" if extra else ""))
    if not ok:
        fail += 1


# —— 页面门控：未登录 302 到 /login?next=... ——
r = client.get("/", follow_redirects=False)
check("未登录访问主页 302", r.status_code == 302, str(r.status_code))
check("重定向到登录页", r.headers.get("location", "").startswith("/login?next="), r.headers.get("location", ""))
check("未登录访问图库页 302", client.get("/gallery", follow_redirects=False).status_code == 302)
check("未登录访问帖子页 302", client.get("/forum/123", follow_redirects=False).status_code == 302)
check("未登录访问周报入口 302", client.get("/weekly", follow_redirects=False).status_code == 302)

r = client.get("/forum/new?id=5", follow_redirects=False)
check("查询串完整进入 next", "next=%2Fforum%2Fnew%3Fid%3D5" in r.headers.get("location", ""), r.headers.get("location", ""))

# —— cookie / Bearer 双通道 ——
check("有效 cookie 访问主页 200", client.get("/", cookies=COOKIE, follow_redirects=False).status_code == 200)
check("仅 Bearer 头访问页面 200（有效密钥即登录）", client.get("/", headers=AUTH, follow_redirects=False).status_code == 200)
check("Bearer 头调 API 200", client.get("/api/timeline", headers=AUTH).status_code == 200)
check("仅 cookie 调 API 200（依赖层 cookie 兜底）", client.get("/api/timeline", cookies=COOKIE).status_code == 200)

# —— API/媒体未登录 401 JSON（非重定向）——
r = client.get("/api/timeline")
check("未登录调 API 401", r.status_code == 401, str(r.status_code))
check("401 返回 JSON", r.headers.get("content-type", "").startswith("application/json"))
check("未登录调公开读 API 也 401（全站锁死）", client.get("/api/checkins").status_code == 401)
check("未登录取原图 401", client.get("/media/123/x.jpg").status_code == 401)
check("未登录取缩略图 401", client.get("/thumb/123/x.jpg").status_code == 401)
check("未登录取论坛图片 401", client.get("/forum/media/x.jpg").status_code == 401)
check("未登录取活动作品 401", client.get("/archive/1/media/x.jpg").status_code == 401)

# —— 白名单 ——
check("登录页免鉴权 200", client.get("/login").status_code == 200)
check("登录 API 密钥错误 401（路由而非门控）", client.post("/api/auth/login", json={"key": "garbage"}).status_code == 401)
check("静态页面资源放行", client.get("/static/login.html").status_code == 200)
check("共享静态放行", client.get("/shared/auth.js").status_code == 200)

with patch("webapp.app.resolve_display_name", return_value="测试用户"), \
     patch("webapp.app.resolve_avatar_url", return_value=""):
    check("登录 API 正确密钥 200", client.post("/api/auth/login", json={"key": KEY}).status_code == 200)

# —— bot 事件上报（独立事件令牌，穿透门控）——
EVENT = {
    "id": f"test:{uuid.uuid4().hex}",
    "source": "test",
    "actor": {"id": "1"},
    "display": {"title": "门控测试"},
}
r = client.post("/api/timeline/events", headers={"Authorization": f"Bearer {TIMELINE_TOKEN}"}, json=EVENT)
check("事件令牌上报穿透门控", r.status_code == 200, r.text[:80])
check("无令牌上报 401", client.post("/api/timeline/events", json=EVENT).status_code == 401)

print("ALL PASS" if not fail else f"{fail} FAILED")
sys.exit(1 if fail else 0)
