"""赞赏页（收款码展示）回归：登录门控、目录扫描列表、媒体路由与路径穿越防护。

收款码图片由站长手动上传到 donate 目录（config paths.donate，默认
server_data/donate/），页面按目录内容自动展示，无管理后台。

独立进程运行: python test/scripts/check_donate_page.py
（pytest 由 test/test_webapp_api_suites.py 子进程自动纳入统一回归）
"""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_donate_test_")
_db = os.path.join(_tmp, "data.db")
_donate = os.path.join(_tmp, "donate")
sys.path.insert(0, str(PROJECT_ROOT / "test" / "scripts"))
from _env import write_config  # noqa: E402

os.environ["BOTERO_CONFIG"] = write_config(_tmp, paths={"donate": _donate})

_conn = sqlite3.connect(_db)
from core.database_manager import init_schema  # noqa: E402

init_schema(_conn, _conn.cursor())
_conn.commit()

from fastapi.testclient import TestClient  # noqa: E402
from core import config  # noqa: E402
from core.auth import make_login_key  # noqa: E402
from webapp.app import app  # noqa: E402

ME = "12345601"
MH = {"Authorization": "Bearer " + make_login_key(int(ME))}
client = TestClient(app)
fail = 0

WEIRD = "打赏码 (2).png"  # 文件名含空格括号：锁定前端 encodeURIComponent 链路同款编码约定
PLAIN = "alipay.jpg"


def check(name, ok, extra=""):
    global fail
    print(f"{'ok' if ok else 'FAIL'} - {name}" + (f" {extra}" if extra else ""))
    if not ok:
        fail += 1


# —— 种收款码图片（站长手动上传的模拟）——
assert Path(str(config.DONATE_DIR)) == Path(_donate), "paths.donate 重定向未生效"
os.makedirs(_donate, exist_ok=True)
png = b"\x89PNG\r\n\x1a\n-fake-bytes"
(Path(_donate) / PLAIN).write_bytes(png)
(Path(_donate) / WEIRD).write_bytes(png)
(Path(_donate) / "notes.txt").write_bytes(b"not an image")  # 非图片不展示

# --- 门控 ---
r = client.get("/donate", follow_redirects=False)
check("page 未登录 302", r.status_code == 302 and r.headers.get("location", "").startswith("/login"),
      str(r.status_code))
r = client.get("/api/donate/images")
check("api 未登录 401", r.status_code == 401, str(r.status_code))
r = client.get(f"/donate/media/{quote(PLAIN)}")
check("media 未登录 401", r.status_code == 401, str(r.status_code))

# --- 页面与列表 ---
r = client.get("/donate", headers=MH)
check("page 200", r.status_code == 200 and "赞赏" in r.text, str(r.status_code))
r = client.get("/api/donate/images", headers=MH)
check("api 200", r.status_code == 200, str(r.status_code))
check("列表=目录内全部图片（排序）", r.json().get("images") == sorted([PLAIN, WEIRD]),
      str(r.json()))

# --- 媒体路由 ---
r = client.get(f"/donate/media/{quote(WEIRD)}", headers=MH)
check("media 特殊文件名 200", r.status_code == 200 and r.content == png, str(r.status_code))
r = client.get("/donate/media/nope.png", headers=MH)
check("media 缺失 404", r.status_code == 404, str(r.status_code))
r = client.get("/donate/media/%2e%2e%2fconfig.yaml", headers=MH)
# httpx 客户端侧已归一化点段，穿越载荷实际到不了路由；断言永不 200 泄漏即可
check("路径穿越拦截", r.status_code in (400, 404), str(r.status_code))

print(f"\n{'PASS' if fail == 0 else 'FAIL'}: {fail} failures")
sys.exit(0 if fail == 0 else 1)
