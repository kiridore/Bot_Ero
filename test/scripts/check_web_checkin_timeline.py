"""网页打卡 → 时间线事件 全链路回归（真实 HTTP 自回环）。

复现 2026-09 的静默丢事件 bug：async 路由内同步 emit 自 POST 本进程，事件循环
被阻塞导致互相等待双双超时。本脚本起真实 uvicorn（临时配置，timeline.url 指回
同端口），打卡后断言 timeline_events 落库且响应不超时。

独立进程运行: python test/scripts/check_web_checkin_timeline.py
"""

import json
import os
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
import zlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_checkin_tl_")
sys.path.insert(0, str(PROJECT_ROOT / "test" / "scripts"))
from _env import write_config  # noqa: E402

PORT = 8791
os.environ["BOTERO_CONFIG"] = write_config(
    _tmp, timeline={"url": f"http://127.0.0.1:{PORT}", "token": "test-timeline-token"}
)

from core import config  # noqa: E402
from core.auth import make_login_key  # noqa: E402


def check(name, ok, extra=""):
    global fail
    print(f"{'ok' if ok else 'FAIL'} - {name}" + (f" {extra}" if extra else ""))
    if not ok:
        fail += 1


fail = 0

# 造一张最小 PNG
def _png() -> bytes:
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x30\x60\x90" * 4 for _ in range(4))
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


server = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "webapp.app:app",
     "--host", "127.0.0.1", "--port", str(PORT), "--log-level", "warning"],
    cwd=str(PROJECT_ROOT), env=dict(os.environ, PYTHONIOENCODING="utf-8"),
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
try:
    base = f"http://127.0.0.1:{PORT}"
    ready = False
    for _ in range(40):
        try:
            urllib.request.urlopen(base + "/login", timeout=2)
            ready = True
            break
        except Exception:
            time.sleep(0.5)
    check("服务器就绪", ready)
    if not ready:
        print(f"\n{'FAIL: server not started'}")
        sys.exit(1)

    key = make_login_key("555666")
    body = (
        b"--XX\r\nContent-Disposition: form-data; name=\"files\"; filename=\"a.png\"\r\n"
        b"Content-Type: image/png\r\n\r\n" + _png() + b"\r\n--XX--\r\n"
    )
    r = urllib.request.Request(base + "/api/me/checkin", data=body, method="POST")
    r.add_header("Content-Type", "multipart/form-data; boundary=XX")
    r.add_header("Authorization", "Bearer " + key)
    t0 = time.time()
    resp = urllib.request.urlopen(r, timeout=30)
    payload = json.loads(resp.read().decode())
    elapsed = time.time() - t0
    check("打卡成功", resp.status == 200 and payload.get("success") is True)
    check("响应不卡顿（<5s，无自回环死锁）", elapsed < 5, f"{elapsed:.2f}s")

    time.sleep(1.0)  # best-effort 发送完成落库
    conn = sqlite3.connect(str(config.DB_PATH))
    rows = conn.execute(
        "SELECT dedup_key FROM timeline_events WHERE source='checkin' ORDER BY rowid DESC LIMIT 1"
    ).fetchall()
    conn.close()
    check("时间线事件已落库", bool(rows) and rows[0][0].startswith("checkin:555666:"),
          rows[0][0] if rows else "(none)")
finally:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()

print(f"\n{'ALL PASS' if fail == 0 else f'{fail} FAILED'}")
sys.exit(1 if fail else 0)
