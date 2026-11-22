"""打卡图库按查看者应用打卡隐私设置回归（与时间线同口径）。

背景：时间线已按作者 `checkin_display()`（show|blur|text|hidden）对非作者变换图片，
图库 `/api/checkins` 却始终下发原图。修复口径（Q1:A / Q2:A 裁决）：
- 作者本人：全部记录原样下发（text/hidden 的应用户也可见）；
- 非作者 + show：`/thumb/…` + `/media/…`（与改动前一致）；
- 非作者 + blur：两支 URL 都是 `/thumb/…?blur=1`，不给任何 `/media/` 原图路径；
- 非作者 + text/hidden：条目不下发，`total`/`has_more` 同步扣除（过滤在切片前）。
媒体路由 `/thumb`、`/media` 本次**不做**服务端强制（已知边界，见 specs/web-gallery.md）。

独立进程运行: python test/scripts/check_gallery_privacy.py
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

_tmp = tempfile.mkdtemp(prefix="botero_gallery_privacy_")
_db = os.path.join(_tmp, "data.db")
sys.path.insert(0, str(PROJECT_ROOT / "test" / "scripts"))
from _env import write_config  # noqa: E402

os.environ["BOTERO_CONFIG"] = write_config(
    _tmp,
    paths={"db": _db, "images": os.path.join(_tmp, "record_images")},
)

from fastapi.testclient import TestClient  # noqa: E402
from core import config  # noqa: E402
from core.auth import make_login_key  # noqa: E402
from core.database_manager import init_schema  # noqa: E402
from core.user_settings import update_settings  # noqa: E402
from webapp.app import app  # noqa: E402

AUTHOR = "32870101"
VIEWER = "32870102"
OTHER = "32870103"  # 第三个作者：默认 show（无设置文件）
client = TestClient(app)


def headers(uid: str) -> dict:
    return {"Authorization": "Bearer " + make_login_key(int(uid))}


def check(name, ok, extra=""):
    global fail
    print(f"{'ok' if ok else 'FAIL'} - {name}" + (f" {extra}" if extra else ""))
    if not ok:
        fail += 1


fail = 0


def _png(w=8, h=6):
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x30\x60\x90" * w for _ in range(h))
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


_conn = sqlite3.connect(_db)
init_schema(_conn, _conn.cursor())
_conn.commit()

# —— 种打卡记录：作者 A 私聊 ×1 + 群聊 ×1；作者 OTHER 群聊 ×1 ——
RECORDS = [
    (AUTHOR, 0, "a_group.png", "2026-09-01 12:00:00"),
    (AUTHOR, 1, "a_private.png", "2026-09-02 12:00:00"),
    (OTHER, 0, "c_group.png", "2026-09-03 12:00:00"),
]
for uid, is_private, name, when in RECORDS:
    folder = Path(str(config.IMAGE_ROOT)) / uid
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(_png())
    _conn.execute(
        "INSERT INTO checkin_records (user_id, checkin_date, content, is_private)"
        " VALUES (?, ?, ?, ?)",
        (int(uid), when, name, is_private),
    )
_conn.commit()


def display(state_private: str, state_group: str) -> None:
    """写作者 A 的两类打卡显示状态（走真实设置文件，不走内存桩）。"""
    update_settings(
        AUTHOR,
        {"privacy": {"checkin_display_private": state_private,
                     "checkin_display_group": state_group}},
    )


def items_of(viewer: str, **params) -> dict:
    query = {"only_with_file": "true"}
    query.update(params)
    res = client.get("/api/checkins", params=query, headers=headers(viewer))
    if res.status_code != 200:
        check(f"gallery 200 (viewer={viewer})", False, str(res.status_code))
        return {}
    return res.json()


def by_content(payload: dict, name: str):
    return next(
        (i for i in payload.get("items", []) if i["image_url"].split("?")[0].endswith(name)),
        None,
    )


def by_date(payload: dict, day: str):
    return next(
        (i for i in payload.get("items", []) if str(i["checkin_date"]).startswith(day)),
        None,
    )


# ============ 1. show（缺省）：非作者与改动前完全一致 ============
payload = items_of(VIEWER, user_id=AUTHOR)
group = by_content(payload, "/a_group.png")
private = by_content(payload, "/a_private.png")
check("show: 非作者拿到 2 条", len(payload["items"]) == 2 and payload["total"] == 2,
      f'{len(payload["items"])}/{payload["total"]}')
check("show: thumbnail_url 为原缩略图",
      group is not None and group["thumbnail_url"] == f"/thumb/{AUTHOR}/a_group.png",
      str(group and group["thumbnail_url"]))
check("show: image_url 为原图",
      group is not None and group["image_url"] == f"/media/{AUTHOR}/a_group.png",
      str(group and group["image_url"]))
check("show: 私聊记录同样原图",
      private is not None and private["image_url"] == f"/media/{AUTHOR}/a_private.png",
      str(private and private["image_url"]))

# ============ 2. blur：两支 URL 都是模糊缩略图，不泄露原图路径 ============
display("show", "blur")
payload = items_of(VIEWER, user_id=AUTHOR)
group = by_content(payload, "/a_group.png")
private = by_content(payload, "/a_private.png")
blur_url = f"/thumb/{AUTHOR}/a_group.png?blur=1"
check("blur: 非作者仍能看到该条目", group is not None)
check("blur: thumbnail_url 为模糊图",
      group is not None and group["thumbnail_url"] == blur_url,
      str(group and group["thumbnail_url"]))
check("blur: image_url 也是模糊图（不给 /media/）",
      group is not None and group["image_url"] == blur_url,
      str(group and group["image_url"]))
check("blur: 另一类型仍按自己的设置（show）",
      private is not None and private["image_url"] == f"/media/{AUTHOR}/a_private.png",
      str(private and private["image_url"]))

author_view = items_of(AUTHOR, user_id=AUTHOR)
author_group = by_content(author_view, "/a_group.png")
check("blur: 作者本人仍是原图",
      author_group is not None
      and author_group["thumbnail_url"] == f"/thumb/{AUTHOR}/a_group.png"
      and author_group["image_url"] == f"/media/{AUTHOR}/a_group.png",
      str(author_group and (author_group["thumbnail_url"], author_group["image_url"])))

# ============ 3. text / hidden：卡片照出，图片位为空串 ============
for state in ("text", "hidden"):
    display(state, "show")
    payload = items_of(VIEWER, user_id=AUTHOR)
    private = by_date(payload, "2026-09-02")
    check(f"{state}: 非作者仍看到卡片", private is not None)
    check(f"{state}: 图片位两支 URL 为空串",
          private is not None and private["thumbnail_url"] == "" and private["image_url"] == "",
          str(private and (private["thumbnail_url"], private["image_url"])))
    check(f"{state}: has_file 仍按磁盘文件为 true",
          private is not None and private["has_file"] is True,
          str(private and private["has_file"]))
    check(f"{state}: 卡片信息（昵称/日期）照常下发",
          private is not None and private["display_name"] != ""
          and private["checkin_date"].startswith("2026-09-02"),
          str(private and (private["display_name"], private["checkin_date"])))
    check(f"{state}: total 不扣除占位卡",
          payload.get("total") == 2 and len(payload.get("items", [])) == 2,
          f'total={payload.get("total")} items={len(payload.get("items", []))}')
    author_payload = items_of(AUTHOR, user_id=AUTHOR)
    check(f"{state}: 作者本人仍是原图",
          by_content(author_payload, "/a_private.png") is not None
          and author_payload.get("total") == 2,
          f'total={author_payload.get("total")}')

# ============ 4. 两类打卡各取自己的设置（分流，而非取更严者）============
display("blur", "show")
payload = items_of(VIEWER, user_id=AUTHOR)
private = by_content(payload, "/a_private.png")
group = by_content(payload, "/a_group.png")
check("分流: 私聊 blur → 私聊模糊",
      private is not None
      and private["image_url"] == f"/thumb/{AUTHOR}/a_private.png?blur=1",
      str(private and private["image_url"]))
check("分流: 群聊 show → 群聊原图",
      group is not None and group["image_url"] == f"/media/{AUTHOR}/a_group.png",
      str(group and group["image_url"]))

display("show", "blur")
payload = items_of(VIEWER, user_id=AUTHOR)
private = by_content(payload, "/a_private.png")
group = by_content(payload, "/a_group.png")
check("分流: 对调后私聊原图",
      private is not None and private["image_url"] == f"/media/{AUTHOR}/a_private.png",
      str(private and private["image_url"]))
check("分流: 对调后群聊模糊",
      group is not None and group["image_url"] == f"/thumb/{AUTHOR}/a_group.png?blur=1",
      str(group and group["image_url"]))

# ============ 5. total / 分页：占位卡计入统计 ============
display("text", "blur")  # A：群聊 blur（模糊）、私聊 text（占位）；OTHER 默认 show
full = items_of(VIEWER)
check("分页: total 为全部记录数（含占位卡）", full.get("total") == 3, f'total={full.get("total")}')
page1 = items_of(VIEWER, page=1, page_size=2)
page2 = items_of(VIEWER, page=2, page_size=2)
check("分页: 第一页 2 条且 has_more",
      len(page1.get("items", [])) == 2 and page1.get("has_more") is True,
      f'items={len(page1.get("items", []))} has_more={page1.get("has_more")}')
check("分页: 第二页 1 条且无更多",
      len(page2.get("items", [])) == 1 and page2.get("has_more") is False,
      f'items={len(page2.get("items", []))} has_more={page2.get("has_more")}')
check("分页: 每页 total 一致",
      page1.get("total") == 3 and page2.get("total") == 3,
      f'{page1.get("total")}/{page2.get("total")}')

# ============ 6. 媒体路由不变（Q1:A 已知边界：直链仍可取原图）============
rt = client.get(f"/thumb/{AUTHOR}/a_private.png?blur=1", headers=headers(VIEWER))
check("媒体: 模糊缩略图端点 200", rt.status_code == 200, str(rt.status_code))
rm = client.get(f"/media/{AUTHOR}/a_private.png", headers=headers(VIEWER))
check("媒体: 原图端点行为不变（已知边界）",
      rm.status_code == 200 and rm.content[:8] == b"\x89PNG\r\n\x1a\n",
      str(rm.status_code))

# ============ 7. 个人中心本人列表不受影响 ============
res = client.get("/api/me/checkins?page=1", headers=headers(AUTHOR))
me = res.json() if res.status_code == 200 else {}
check("个人中心: 本人列表仍是原图",
      res.status_code == 200
      and any(i["image_url"] == f"/media/{AUTHOR}/a_private.png" for i in me.get("items", [])),
      str(res.status_code))

print(f"\n{'PASS' if fail == 0 else 'FAIL'}: {fail} failures")
sys.exit(0 if fail == 0 else 1)
