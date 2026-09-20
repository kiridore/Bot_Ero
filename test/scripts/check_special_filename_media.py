"""特殊字符打卡图文件名（QQ 原始名含 $ [ ] % 等）URL 编码回归。

背景：打卡图文件名原样拼进 /media/ /thumb/ URL，未做 percent-encoding；
含 % 的名字（如 S$Y6V]1L]HO]]R%1RP8ML.png，%1R 为非法转义）会被 Caddy
反代直接 400，时间线与打卡图库均无法显示。修复口径：
- gallery / profile 生成 URL 时对文件名 quote；
- 时间线 serve 时对存量 data.images 做 quote(unquote()) 幂等归一（旧事件
  存的是未编码 URL，无法迁移，读侧统一编码）。

独立进程运行: python test/scripts/check_special_filename_media.py
（pytest 由 test/test_webapp_api_suites.py 子进程自动纳入统一回归）
"""

import json
import os
import sqlite3
import struct
import sys
import tempfile
import zlib
from pathlib import Path
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_special_fname_")
_db = os.path.join(_tmp, "data.db")
sys.path.insert(0, str(PROJECT_ROOT / "test" / "scripts"))
from _env import write_config  # noqa: E402

os.environ["BOTERO_CONFIG"] = write_config(_tmp)

_conn = sqlite3.connect(_db)
from core.database_manager import init_schema  # noqa: E402

init_schema(_conn, _conn.cursor())
_conn.commit()

from fastapi.testclient import TestClient  # noqa: E402
from core import config  # noqa: E402
from core.auth import make_login_key  # noqa: E402
from webapp.app import app  # noqa: E402

ME = "328793864"
MH = {"Authorization": "Bearer " + make_login_key(int(ME))}
WEIRD = "S$Y6V]1L]HO]]R%1RP8ML.png"  # 实际线上案例（QQ 图片原始名）
ENC = quote(WEIRD)  # S%24Y6V%5D1L%5DHO%5D%5DR%251RP8ML.png
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


# —— 种特殊文件名图片 + 打卡记录 ——
img_dir = Path(str(config.IMAGE_ROOT)) / ME
img_dir.mkdir(parents=True, exist_ok=True)
(img_dir / WEIRD).write_bytes(_png())
_conn.execute(
    "INSERT INTO checkin_records (user_id, checkin_date, content) VALUES (?, ?, ?)",
    (int(ME), "2026-09-20 12:00:00", WEIRD),
)
# —— 种存量时间线事件（bot 旧版 emit 的未编码 URL，读侧归一的靶子）——
_conn.execute(
    "INSERT INTO timeline_events"
    " (id, source, received_at, actor_id, actor_qq, title, data, dedup_key)"
    " VALUES (?, 'checkin', ?, ?, ?, ?, ?, ?)",
    (
        "checkin:weird1", "2026-09-20 12:00:01", ME, ME,
        "{id:%s} 完成打卡" % ME,
        json.dumps({"images": [f"/thumb/{ME}/{WEIRD}"]}, ensure_ascii=False),
        "checkin:%s:2026-09-20:weird1" % ME,
    ),
)
_conn.commit()

# --- 图库 API：URL 必须 percent-encoded，无裸 %/[/]/$ ---
r = client.get("/api/checkins", headers=MH)
check("gallery 200", r.status_code == 200, str(r.status_code))
items = [i for i in r.json()["items"] if i["user_id"] == ME]
check("gallery item found", len(items) == 1, str(len(items)))
if items:
    it = items[0]
    check("gallery image_url encoded", it["image_url"] == f"/media/{ME}/{ENC}", it["image_url"])
    check("gallery thumb_url encoded", it["thumbnail_url"] == f"/thumb/{ME}/{ENC}", it["thumbnail_url"])

# --- 路由 round-trip：编码 URL 取图/缩略图必须命中磁盘文件 ---
rm = client.get(f"/media/{ME}/{ENC}", headers=MH)
check("media 200 png", rm.status_code == 200 and rm.content[:8] == b"\x89PNG\r\n\x1a\n",
      str(rm.status_code))
rt = client.get(f"/thumb/{ME}/{ENC}", headers=MH)
check("thumb 200", rt.status_code == 200, str(rt.status_code))

# --- 个人中心打卡列表：同款编码 ---
rp = client.get("/api/me/checkins?page=1", headers=MH)
check("profile 200", rp.status_code == 200, str(rp.status_code))
pitems = [i for i in rp.json().get("items", []) if i["checkin_date"].startswith("2026-09-20")]
if pitems:
    check("profile image_url encoded", pitems[0]["image_url"] == f"/media/{ME}/{ENC}",
          pitems[0]["image_url"])
    check("profile thumb_url encoded", pitems[0]["thumbnail_url"] == f"/thumb/{ME}/{ENC}",
          pitems[0]["thumbnail_url"])
else:
    check("profile item found", False)

# --- 时间线：存量未编码 data.images 读侧归一为编码 URL ---
rtm = client.get("/api/timeline", headers=MH)
check("timeline 200", rtm.status_code == 200, str(rtm.status_code))
ev = next((e for e in rtm.json()["events"] if e["id"] == "checkin:weird1"), None)
if ev:
    imgs = (ev.get("data") or {}).get("images", [])
    check("timeline image normalized", imgs == [f"/thumb/{ME}/{ENC}"], str(imgs))
else:
    check("timeline event found", False)

print(f"\n{'PASS' if fail == 0 else 'FAIL'}: {fail} failures")
sys.exit(0 if fail == 0 else 1)
