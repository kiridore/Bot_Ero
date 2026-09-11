"""个人中心打卡列表分页 + 分享卡生成 API 回归。

独立进程运行: python test/scripts/check_profile_checkins.py
（pytest 由 test/test_webapp_api_suites.py 子进程自动纳入统一回归）
"""

import os
import sqlite3
import struct
import sys
import tempfile
import zlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_profile_checkins_")
_db = os.path.join(_tmp, "test.db")
sys.path.insert(0, str(PROJECT_ROOT / "test" / "scripts"))
from _env import write_config  # noqa: E402

os.environ["BOTERO_CONFIG"] = write_config(
    _tmp,
    paths={"db": _db, "images": os.path.join(_tmp, "record_images")},
    thumbs={"cache_dir": os.path.join(_tmp, "thumb_cache")},
)

from core import config  # noqa: E402
from core.database_manager import init_schema  # noqa: E402

_conn = sqlite3.connect(_db)
init_schema(_conn, _conn.cursor())
_conn.commit()

from fastapi.testclient import TestClient  # noqa: E402
from core.auth import make_login_key  # noqa: E402
from webapp.app import app  # noqa: E402

ME = "12345601"
OTHER = "12345602"
MH = {"Authorization": "Bearer " + make_login_key(int(ME))}
OH = {"Authorization": "Bearer " + make_login_key(int(OTHER))}
client = TestClient(app)
fail = 0


def check(name, ok, extra=""):
    global fail
    print(f"{'ok' if ok else 'FAIL'} - {name}" + (f" {extra}" if extra else ""))
    if not ok:
        fail += 1


def _png(w=8, h=6):
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x30\x60\x90" * w for _ in range(h))
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


img_dir = Path(str(config.IMAGE_ROOT)) / ME
img_dir.mkdir(parents=True, exist_ok=True)

rows = []
for i in range(25):  # 25 条带文件记录（跨两页）
    name = f"card{i:02d}.png"
    (img_dir / name).write_bytes(_png())
    rows.append((int(ME), f"2026-03-{(i % 28) + 1:02d} 12:00:00", name))
rows.append((int(ME), "2026-03-05 13:00:00", "missing.png"))     # 文件不存在
rows.append((int(ME), "2026-03-06 14:00:00", "remedy_checkin"))   # 补卡行，非图片
cur = _conn.cursor()
cur.executemany(
    "INSERT INTO checkin_records (user_id, checkin_date, content) VALUES (?, ?, ?)", rows
)
_conn.commit()

# --- 列表分页 ---
r1 = client.get("/api/me/checkins?page=1", headers=MH)
check("page1 200", r1.status_code == 200, str(r1.status_code))
d1 = r1.json()
check("page1 24 items", len(d1["items"]) == 24, str(len(d1["items"])))
check("page1 has_more", d1["has_more"] is True)
check("page1 date desc", d1["items"][0]["checkin_date"] >= d1["items"][-1]["checkin_date"])
check(
    "item shape",
    all(k in d1["items"][0] for k in ("id", "checkin_date", "thumbnail_url", "image_url")),
)

r2 = client.get("/api/me/checkins?page=2", headers=MH)
d2 = r2.json()
check("page2 1 item", len(d2["items"]) == 1, str(len(d2["items"])))
check("page2 no more", d2["has_more"] is False)

rid = d1["items"][0]["id"]

# --- 分享卡 ---
rs = client.get(f"/api/me/checkin/{rid}/share.png", headers=MH)
check("share 200", rs.status_code == 200, str(rs.status_code))
check("share content-type png", rs.headers.get("content-type", "").startswith("image/png"))
check("share png magic", rs.content[:8] == b"\x89PNG\r\n\x1a\n", repr(rs.content[:8]))
check("share size bound", len(rs.content) < 4 * 1024 * 1024)

ro = client.get(f"/api/me/checkin/{rid}/share.png", headers=OH)
check("他人记录 404", ro.status_code == 404, str(ro.status_code))
r404 = client.get("/api/me/checkin/999999/share.png", headers=MH)
check("不存在 404", r404.status_code == 404, str(r404.status_code))

mid = cur.execute("SELECT id FROM checkin_records WHERE content='missing.png'").fetchone()[0]
rm = client.get(f"/api/me/checkin/{mid}/share.png", headers=MH)
check("无文件 404", rm.status_code == 404, str(rm.status_code))

ra = client.get("/api/me/checkins?page=1")
check("未登录 401", ra.status_code == 401, str(ra.status_code))

print(f"\n{'PASS' if fail == 0 else 'FAIL'}: {fail} failures")
sys.exit(0 if fail == 0 else 1)
