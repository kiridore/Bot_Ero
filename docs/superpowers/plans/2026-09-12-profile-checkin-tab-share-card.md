# 个人中心打卡卡片 Tab 与分享卡 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 个人主页新增「打卡记录」Tab（与称号并列、月分组卡片网格），并支持为任意打卡图生成尺寸恒定上界的 PIL 分享卡。

**Architecture:** 后端新增两个 `/api/me/*` 路由（分页列表复用 gallery repository；分享卡由新 `core/gen_image/checkin_share_card.py` 纯函数合成，webapp 侧新 `share_service.py` 组装数据）；前端把现有称号区搬入 Tab 面板并新增打卡网格 + lightbox 分享按钮 + 预览下载弹层。

**Tech Stack:** FastAPI（同步路由，线程池自动执行）+ Pillow + 原生 JS/CSS（无框架）。

**Spec:** `docs/superpowers/specs/2026-09-12-profile-checkin-tab-share-card-design.md`

## Global Constraints

- **Commit 纪律（覆盖 skill 默认的逐任务提交）**：本仓库惯例 = 一个特性一个 commit（先例 `a47efb4`：代码+测试+CHANGELOG+版本同一 commit）。Task 1–3 只改代码跑测试、**不提交**；Task 4 统一做唯一 feature commit。
- bot 进程禁止 async/await；webapp 同步 `def` 路由合法（FastAPI 自动入线程池）。
- 一律 `?` 参数化 SQL，禁止 f-string SQL。
- `checkin_records.user_id` 是 **INTEGER** 列：新 SQL 传 `int(user_id)`（SQLite 亲和性对 text 参数宽容，但显式 int 最稳）。
- 用户可见文案改动同 commit 更新测试断言；纯 webapp 功能不动 `plugins/menu/bot_menu_text.py`。
- 版本：`core/config.py::BOTERO_VERSION` 当前 `1.45.2` → bump 到 `1.46.0`（新功能 minor）。
- 脚本式测试 MUST 用 `test/scripts/_env.py::write_config` 生成临时配置并经 `BOTERO_CONFIG` 指向，绝不触碰真实 `server_data`。
- 前端静态文件名全局唯一；`core/web/static/profile.css` 改动需 bump `profile.html` 里的 `?v=` 缓存参数。
- 前端登录态：`GalleryAuth.save` 会写根域 cookie `botero_key`，故 `<img src="/api/...">` 与 `<a download href="/api/...">` 天然带凭证，无需 fetch blob。

---

### Task 1: 分享卡生成纯函数模块

**Files:**
- Create: `core/gen_image/checkin_share_card.py`
- Test: `test/test_checkin_share_card.py`

**Interfaces:**
- Consumes: `core.gen_image.fonts.load_font / text_width / truncate_text`、`core.gen_image.avatar_helper.raster_circle_avatar_on_rgb`、`core.config.NICKNAME`
- Produces: `build_checkin_share_card(*, display_name: str, checkin_date: str, photo: PIL.Image.Image, avatar: PIL.Image.Image | None = None, streak_days: int = 0, total_images: int = 0) -> PIL.Image.Image`（RGB，宽恒 1080，总高 ≤ 1700）。Task 2 的 `share_service.py` 按此签名调用。

- [ ] **Step 1: 写失败的单测**

创建 `test/test_checkin_share_card.py`（进程内 unittest，conftest 已提供临时 config，无 DB 依赖）：

```python
"""打卡分享卡生成：尺寸上界与宽高比约束（spec D4/D5/D8）。"""

import unittest

from PIL import Image

from core.gen_image.checkin_share_card import (
    CARD_W,
    PHOTO_BOX_H_MAX,
    build_checkin_share_card,
)


def _photo(w, h, mode="RGB"):
    return Image.new(mode, (w, h), (120, 160, 200))


def _build(photo):
    return build_checkin_share_card(
        display_name="测试用户",
        checkin_date="2026-09-12 14:23:11",
        photo=photo,
        streak_days=3,
        total_images=42,
    )


class BuildCheckinShareCardTest(unittest.TestCase):
    def test_width_fixed_height_bounded_square(self):
        card = _build(_photo(2000, 2000))
        self.assertEqual(card.width, CARD_W)
        self.assertLessEqual(card.height, 1700)

    def test_extreme_panorama_bounded(self):
        card = _build(_photo(8000, 400))
        self.assertEqual(card.width, CARD_W)
        self.assertLessEqual(card.height, 1700)

    def test_extreme_tall_bounded(self):
        card = _build(_photo(600, 6000))
        self.assertEqual(card.width, CARD_W)
        self.assertLessEqual(card.height, 1700)

    def test_height_monotonic_then_clamped(self):
        # 照片区随图变高而变高，触顶后被 PHOTO_BOX_H_MAX 钳制
        h_wide = _build(_photo(1000, 500)).height
        h_square = _build(_photo(1000, 1000)).height
        h_tall = _build(_photo(500, 1000)).height
        h_taller = _build(_photo(500, 1500)).height
        h_max = _build(_photo(500, 4000)).height
        self.assertLess(h_wide, h_square)
        self.assertLess(h_square, h_tall)
        self.assertEqual(h_taller, h_max)  # 500x1500 与 500x4000 都触顶 1250
        self.assertLess(h_tall, h_taller)

    def test_alpha_png_flattened_to_rgb(self):
        card = _build(_photo(300, 200, "RGBA"))
        self.assertEqual(card.mode, "RGB")
        self.assertLessEqual(card.height, 1700)

    def test_box_max_constant(self):
        self.assertEqual((CARD_W, PHOTO_BOX_H_MAX), (1080, 1250))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest test/test_checkin_share_card.py -v`
Expected: FAIL（`ModuleNotFoundError: core.gen_image.checkin_share_card`）

- [ ] **Step 3: 实现模块**

创建 `core/gen_image/checkin_share_card.py`：

```python
"""打卡分享卡片：浅色卡 + contain 照片区。

极端宽高比（全景横图/超长截图）不裁剪：原图 contain 缩放进 1000×[240,1250]
照片区，空隙用放大模糊的同图背景铺满，成品宽恒 1080、总高有上界（spec D4/D5）。
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from core.config import NICKNAME
from core.gen_image.avatar_helper import raster_circle_avatar_on_rgb
from core.gen_image.fonts import load_font, text_width, truncate_text

CARD_BG = (245, 245, 245)
TEXT_MAIN = (45, 45, 45)
TEXT_DIM = (110, 110, 110)
INITIAL_BG = (225, 228, 233)

CARD_W = 1080
H_PAD = 40
V_PAD_TOP = 36
AVATAR_SIZE = 96
AVATAR_GAP = 20
NAME_SIZE = 40
DATE_SIZE = 28
STATS_SIZE = 30
FOOTER_SIZE = 26

PHOTO_BOX_W = CARD_W - H_PAD * 2  # 1000
PHOTO_BOX_H_MAX = 1250
PHOTO_BOX_H_MIN = 240
PHOTO_TOP_GAP = 24
NAME_DATE_GAP = 12
STATS_PAD_V = 28
FOOTER_PAD_TOP = 16
FOOTER_PAD_BOTTOM = 32

_WEEKDAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
FOOTER_TEXT = f"Power by {NICKNAME}"


def _flatten_rgb(photo: Image.Image) -> Image.Image:
    """EXIF 摆正 + alpha 合成到白底，输出 RGB（spec D8）。"""
    img = ImageOps.exif_transpose(photo)
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        base = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        img = Image.alpha_composite(base, rgba)
    return img.convert("RGB")


def _photo_block(photo: Image.Image, box_w: int, box_h: int) -> Image.Image:
    """模糊放大同图铺底 + contain 前景居中（微信分享卡惯例）。"""
    bg = ImageOps.fit(photo, (box_w, box_h), method=Image.Resampling.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(40))
    bg = ImageEnhance.Brightness(bg).enhance(1.08)
    ratio = min(box_w / photo.width, box_h / photo.height)
    fg_size = (max(1, round(photo.width * ratio)), max(1, round(photo.height * ratio)))
    fg = photo.resize(fg_size, Image.Resampling.LANCZOS)
    bg.paste(fg, ((box_w - fg_size[0]) // 2, (box_h - fg_size[1]) // 2))
    return bg


def _format_date(checkin_date: str) -> str:
    try:
        d = dt.datetime.strptime(checkin_date, "%Y-%m-%d %H:%M:%S")
        return f"{d:%Y-%m-%d} {_WEEKDAYS[d.weekday()]} {d:%H:%M}"
    except ValueError:
        return checkin_date


def _initial_avatar_tile(name: str) -> Image.Image:
    tile = Image.new("RGB", (AVATAR_SIZE, AVATAR_SIZE), INITIAL_BG)
    font = load_font(44)
    draw = ImageDraw.Draw(tile)
    ch = (name or "?").strip()[:1] or "?"
    w = text_width(draw, ch, font)
    bbox = draw.textbbox((0, 0), ch, font=font)
    draw.text(((AVATAR_SIZE - w) / 2, (AVATAR_SIZE - bbox[3]) / 2), ch, font=font, fill=TEXT_MAIN)
    return tile


def build_checkin_share_card(
    *,
    display_name: str,
    checkin_date: str,
    photo: Image.Image,
    avatar: Optional[Image.Image] = None,
    streak_days: int = 0,
    total_images: int = 0,
) -> Image.Image:
    photo_rgb = _flatten_rgb(photo)

    font_name = load_font(NAME_SIZE)
    font_date = load_font(DATE_SIZE)
    font_stats = load_font(STATS_SIZE)
    font_footer = load_font(FOOTER_SIZE)
    probe = Image.new("RGB", (1, 1), CARD_BG)
    draw_probe = ImageDraw.Draw(probe)

    name = truncate_text(
        draw_probe,
        (display_name or "").strip() or "打卡用户",
        font_name,
        float(CARD_W - H_PAD * 2 - AVATAR_SIZE - AVATAR_GAP),
    )
    date_str = _format_date(checkin_date)

    name_h = draw_probe.textbbox((0, 0), "名字", font=font_name)[3]
    date_h = draw_probe.textbbox((0, 0), date_str, font=font_date)[3]
    header_h = max(AVATAR_SIZE, name_h + NAME_DATE_GAP + date_h)

    contain_h = round(PHOTO_BOX_W * photo_rgb.height / photo_rgb.width)
    box_h = min(max(contain_h, PHOTO_BOX_H_MIN), PHOTO_BOX_H_MAX)

    stats_line = f"连续打卡 {streak_days} 天 · 累计 {total_images} 张"
    stats_h = draw_probe.textbbox((0, 0), stats_line, font=font_stats)[3]
    footer_h = draw_probe.textbbox((0, 0), FOOTER_TEXT, font=font_footer)[3]

    total_h = (
        V_PAD_TOP
        + header_h
        + PHOTO_TOP_GAP
        + box_h
        + STATS_PAD_V
        + stats_h
        + STATS_PAD_V
        + FOOTER_PAD_TOP
        + footer_h
        + FOOTER_PAD_BOTTOM
    )

    card = Image.new("RGB", (CARD_W, total_h), CARD_BG)
    draw = ImageDraw.Draw(card)

    avatar_src = avatar if avatar is not None else _initial_avatar_tile(display_name)
    circ = raster_circle_avatar_on_rgb(avatar_src, AVATAR_SIZE, background=CARD_BG)
    card.paste(circ, (H_PAD, V_PAD_TOP))

    text_x = H_PAD + AVATAR_SIZE + AVATAR_GAP
    draw.text((text_x, V_PAD_TOP), name, font=font_name, fill=TEXT_MAIN)
    draw.text((text_x, V_PAD_TOP + name_h + NAME_DATE_GAP), date_str, font=font_date, fill=TEXT_DIM)

    photo_y = V_PAD_TOP + header_h + PHOTO_TOP_GAP
    card.paste(_photo_block(photo_rgb, PHOTO_BOX_W, box_h), (H_PAD, photo_y))

    stats_y = photo_y + box_h + STATS_PAD_V
    draw.text((H_PAD, stats_y), stats_line, font=font_stats, fill=TEXT_DIM)

    footer_w = text_width(draw, FOOTER_TEXT, font_footer)
    footer_y = stats_y + stats_h + STATS_PAD_V + FOOTER_PAD_TOP
    draw.text((CARD_W - H_PAD - footer_w, footer_y), FOOTER_TEXT, font=font_footer, fill=TEXT_DIM)

    return card
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest test/test_checkin_share_card.py -v`
Expected: 6 passed

- [ ] **Step 5: 不提交**（仓库单 commit 惯例，Task 4 统一提交）

---

### Task 2: 数据访问 + 两个 API 路由 + 脚本套件

**Files:**
- Modify: `webapp/gallery/repository.py`（文件末尾追加 `fetch_checkin_by_id`）
- Modify: `core/db/checkin.py`（`count_all_days` 方法后追加 `count_images`）
- Create: `webapp/profile/share_service.py`
- Modify: `webapp/profile/app.py`（新增两路由 + import）
- Test: `test/scripts/check_profile_checkins.py`（新建脚本套件，`test/test_webapp_api_suites.py` 自动发现）

**Interfaces:**
- Consumes: Task 1 的 `build_checkin_share_card`（签名见上）；`webapp.gallery.repository.fetch_checkins_paginated(*, user_id, year=None, page=1, page_size=40, only_with_file=True) -> tuple[list[CheckinImage], int, bool]`；`core.onebot_client.resolve_display_name/resolve_avatar_url`
- Produces: `GET /api/me/checkins?page=N` → `{items: [CheckinItemOut], page, has_more}`（每页 24）；`GET /api/me/checkin/{record_id}/share.png` → PNG bytes（非本人/不存在/无文件 → 404）。Task 3 前端按此调用。

- [ ] **Step 1: 写失败的脚本套件**

创建 `test/scripts/check_profile_checkins.py`：

```python
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
```

- [ ] **Step 2: 跑套件确认失败**

Run: `python test/scripts/check_profile_checkins.py`
Expected: 多项 FAIL（404：`/api/me/checkins` 路由不存在）

- [ ] **Step 3: 实现数据访问层**

`webapp/gallery/repository.py` 末尾追加：

```python
def fetch_checkin_by_id(record_id: int) -> Optional[CheckinImage]:
    with _connect() as conn:
        r = conn.execute(
            """
            SELECT id, user_id, checkin_date, content
            FROM checkin_records
            WHERE id = ?
            """,
            (record_id,),
        ).fetchone()
    if r is None:
        return None
    return CheckinImage(
        id=r["id"],
        user_id=str(r["user_id"]),
        checkin_date=r["checkin_date"],
        content=r["content"],
        image_path=resolve_image_path(r["user_id"], r["content"]),
    )
```

`core/db/checkin.py` 在 `count_all_days` 方法后追加：

```python
    def count_images(self, user_id):
        self.cur.execute("""
            SELECT COUNT(*)
            FROM checkin_records
            WHERE user_id = ?
            AND content != 'remedy_checkin'
        """, (int(user_id),))
        row = self.cur.fetchone()
        return 0 if row is None or row[0] is None else int(row[0])
```

- [ ] **Step 4: 实现 share_service**

创建 `webapp/profile/share_service.py`：

```python
"""打卡分享卡组装：查记录 → 头像/统计 → PIL 合成 PNG 字节。"""

from __future__ import annotations

import logging
from io import BytesIO

import requests
from PIL import Image

from core.database_manager import DbManager
from core.gen_image.checkin_share_card import build_checkin_share_card
from core.onebot_client import resolve_avatar_url, resolve_display_name
from webapp.gallery.repository import fetch_checkin_by_id

logger = logging.getLogger(__name__)


def _fetch_avatar(user_id: str) -> Image.Image | None:
    url = resolve_avatar_url(user_id)
    if not url:
        return None
    try:
        r = requests.get(url, timeout=6)
        r.raise_for_status()
        im = Image.open(BytesIO(r.content))
        im.load()
        return im
    except Exception:
        logger.warning("分享卡头像获取失败 user=%s", user_id, exc_info=True)
        return None


def build_share_png(record_id: int, user_id: str) -> bytes | None:
    """记录不存在/非本人/无本地文件/图损坏 → None（路由层转 404）。"""
    rec = fetch_checkin_by_id(record_id)
    if rec is None or rec.user_id != str(user_id) or rec.image_path is None:
        return None
    try:
        photo = Image.open(rec.image_path)
        photo.load()
    except Exception:
        logger.warning("分享卡打卡图读取失败 record=%s path=%s", record_id, rec.image_path, exc_info=True)
        return None

    db = DbManager()
    streaks = db.checkin.streaks(int(user_id))
    card = build_checkin_share_card(
        display_name=resolve_display_name(user_id),
        checkin_date=rec.checkin_date,
        photo=photo,
        avatar=_fetch_avatar(user_id),
        streak_days=streaks["current_daily"],
        total_images=db.checkin.count_images(int(user_id)),
    )
    buf = BytesIO()
    card.save(buf, format="PNG")
    return buf.getvalue()
```

- [ ] **Step 5: 实现路由**

`webapp/profile/app.py`：

import 区改动（在 `from webapp.gallery.repository import CheckinImage, fetch_user_settlement_day` 处合并，并新增 share_service import；`Response` 从 `fastapi.responses` 导入）：

```python
from fastapi.responses import FileResponse, Response
from webapp.gallery.repository import (
    CheckinImage,
    fetch_checkins_paginated,
    fetch_user_settlement_day,
)
from webapp.profile.share_service import build_share_png
```

`CheckinItemOut` 类后追加模型与常量：

```python
class CheckinPageOut(BaseModel):
    page: int
    has_more: bool
    items: list[CheckinItemOut]


CHECKIN_PAGE_SIZE = 24
```

在 `api_my_day` 路由后追加两个路由：

```python
@router.get("/api/me/checkins", response_model=CheckinPageOut)
def api_my_checkins(
    user_id: Annotated[str, Depends(get_current_user_id)],
    page: int = Query(1, ge=1),
):
    items, _total, has_more = fetch_checkins_paginated(
        user_id=user_id, page=page, page_size=CHECKIN_PAGE_SIZE
    )
    name = resolve_display_name(user_id)
    return CheckinPageOut(
        page=page,
        has_more=has_more,
        items=[_checkin_to_out(it, name) for it in items],
    )


@router.get("/api/me/checkin/{record_id}/share.png")
def api_checkin_share_png(
    record_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    data = build_share_png(record_id, user_id)
    if data is None:
        raise HTTPException(status_code=404, detail="打卡记录不存在")
    return Response(content=data, media_type="image/png")
```

- [ ] **Step 6: 跑套件确认通过**

Run: `python test/scripts/check_profile_checkins.py`
Expected: 全部 ok，`PASS: 0 failures`

- [ ] **Step 7: 跑既有相关回归确认无破坏**

Run: `python -m pytest test/test_webapp_api_suites.py test/test_checkin_share_card.py -v`
Expected: 全部 passed（含新套件被自动发现）

- [ ] **Step 8: 不提交**（Task 4 统一提交）

---

### Task 3: 前端 Tab + 卡片网格 + 分享预览

**Files:**
- Modify: `webapp/static/profile.html`（lightbox 加分享按钮；新增分享预览 dialog；bump css `?v=`）
- Modify: `webapp/static/profile.js`（Tab 化、打卡网格、lightbox 带 id、分享弹层）
- Modify: `core/web/static/profile.css`（Tab/网格/卡片/弹层样式）

**Interfaces:**
- Consumes: Task 2 的两个 API；现有 `GalleryAuth.headers()`、`openLightbox`、lightbox/dayDialog 模式
- Produces: DOM 契约 —— `#panelTitles` / `#panelCheckins` 面板、`.profile-tabs button[data-tab]`、`#checkinGrid`、`#checkinMore`、`#shareDialog` / `#shareImg` / `#shareDownload`、`#lightboxShare`

- [ ] **Step 1: profile.html —— lightbox 分享按钮 + 分享预览 dialog**

lightbox（现有）改为：

```html
  <div id="lightbox" class="lightbox hidden" role="dialog" aria-modal="true">
    <button type="button" class="lightbox-close" id="lightboxClose" aria-label="关闭">×</button>
    <button type="button" class="lightbox-share hidden" id="lightboxShare">生成分享卡片</button>
    <figure>
      <img id="lightboxImg" alt="" />
    </figure>
  </div>
```

紧随其后新增：

```html
  <dialog id="shareDialog" class="share-dialog">
    <div class="share-dialog-header">
      <h3>打卡分享卡片</h3>
      <button type="button" id="shareDialogClose" aria-label="关闭">×</button>
    </div>
    <div class="share-dialog-body">
      <img id="shareImg" alt="打卡分享卡片" />
    </div>
    <div class="share-dialog-actions">
      <a id="shareDownload" class="share-download" download="checkin-share.png">下载图片</a>
    </div>
  </dialog>
```

并把 `<link rel="stylesheet" href="/shared/profile.css?v=2" />` bump 为 `?v=3`。

- [ ] **Step 2: profile.css —— 新样式**

`core/web/static/profile.css` 末尾追加（复用既有 CSS 变量 `--paper-card`/`--rule`/`--accent`/`--ink-soft`/`--radius-sm`）：

```css
/* ---- 个人主页 Tab（称号 / 打卡记录） ---- */
.profile-tabs {
  display: flex;
  gap: 0.5rem;
  margin: 1.5rem 0 1rem;
}

.profile-tabs button {
  padding: 0.4rem 1rem;
  font-size: 0.9rem;
  border-radius: 999px;
  border: 1px solid var(--rule);
  background: var(--paper-card);
  color: var(--ink-soft);
  cursor: pointer;
}

.profile-tabs button.active {
  color: var(--accent);
  border-color: var(--accent);
  background: var(--accent-soft);
}

.tab-panel.hidden {
  display: none;
}

/* ---- 打卡记录卡片网格 ---- */
.checkin-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 0.75rem;
}

.checkin-month {
  grid-column: 1 / -1;
  margin: 1rem 0 0.25rem;
  font-size: 0.95rem;
  color: var(--ink-soft);
}

.checkin-card {
  position: relative;
  padding: 0;
  border: 1px solid var(--rule);
  border-radius: var(--radius-sm);
  background: var(--paper-card);
  overflow: hidden;
  cursor: pointer;
}

.checkin-card img {
  display: block;
  width: 100%;
  aspect-ratio: 1 / 1;
  object-fit: cover;
}

.checkin-card-date {
  display: block;
  padding: 0.3rem 0.5rem;
  font-size: 0.75rem;
  color: var(--ink-soft);
  border-top: 1px solid var(--rule);
}

.checkin-more {
  display: block;
  margin: 1rem auto 0;
  padding: 0.4rem 1.4rem;
  font-size: 0.85rem;
  border-radius: 999px;
  border: 1px solid var(--rule);
  background: var(--paper-card);
  color: var(--ink-soft);
  cursor: pointer;
}

.checkin-more:disabled {
  opacity: 0.6;
  cursor: default;
}

/* ---- lightbox 分享按钮 ---- */
.lightbox-share {
  position: fixed;
  left: 50%;
  transform: translateX(-50%);
  bottom: 4.5rem;
  padding: 0.5rem 1.4rem;
  font-size: 0.9rem;
  border-radius: 999px;
  border: 1px solid var(--accent);
  background: var(--paper-card);
  color: var(--accent);
  cursor: pointer;
  z-index: 10;
}

/* ---- 分享预览弹层 ---- */
.share-dialog {
  width: min(92vw, 540px);
  border: 1px solid var(--rule);
  border-radius: var(--radius-sm);
  background: var(--paper-card);
  padding: 0;
}

.share-dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--rule);
}

.share-dialog-header h3 {
  margin: 0;
  font-size: 1rem;
}

.share-dialog-header button {
  border: none;
  background: none;
  font-size: 1.2rem;
  cursor: pointer;
  color: var(--ink-soft);
}

.share-dialog-body {
  padding: 1rem;
  max-height: 65vh;
  overflow-y: auto;
}

.share-dialog-body img {
  display: block;
  width: 100%;
  border-radius: var(--radius-sm);
}

.share-dialog-actions {
  display: flex;
  justify-content: center;
  padding: 0 1rem 1rem;
}

.share-download {
  padding: 0.5rem 1.6rem;
  border-radius: 999px;
  background: var(--accent);
  color: #fff;
  text-decoration: none;
  font-size: 0.9rem;
}
```

（若 `--accent-soft` 变量不存在，参照 `profile.css` 顶部 `.profile-nav a.active` 已用到的同名变量直接使用；它已在该文件出现，无需新增定义。）

- [ ] **Step 3: profile.js —— Tab 状态与打卡网格**

文件顶部状态区（`let titleFilter = "all";` 后）追加：

```js
let activeTab = "titles";
let checkinState = { loaded: false, page: 0, hasMore: true, loading: false, lastMonth: "" };
let currentRecordId = null;
```

`openLightbox` 改为带记录 id：

```js
function openLightbox(url, recordId = null) {
  lightboxImg.src = url;
  currentRecordId = recordId;
  const shareBtn = document.getElementById("lightboxShare");
  if (shareBtn) shareBtn.classList.toggle("hidden", recordId == null);
  lightbox.classList.remove("hidden");
}
```

`openDay` 里图片点击改为 `openLightbox(item.image_url, item.id)`。

新增 Tab 与网格逻辑（放在 `renderTitles` 之后）：

```js
function switchTab(key) {
  if (key === activeTab) return;
  activeTab = key;
  document.querySelectorAll(".profile-tabs button").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === key);
  });
  document.getElementById("panelTitles").classList.toggle("hidden", key !== "titles");
  document.getElementById("panelCheckins").classList.toggle("hidden", key !== "checkins");
  if (key === "checkins" && !checkinState.loaded) {
    checkinState.loaded = true;
    loadCheckins();
  }
}

async function loadCheckins() {
  const more = document.getElementById("checkinMore");
  if (!more || checkinState.loading || !checkinState.hasMore) return;
  checkinState.loading = true;
  more.disabled = true;
  more.textContent = "加载中…";
  try {
    const res = await fetch(`/api/me/checkins?page=${checkinState.page + 1}`, {
      headers: GalleryAuth.headers(),
    });
    if (!res.ok) throw new Error("加载失败");
    const data = await res.json();
    checkinState.page = data.page;
    checkinState.hasMore = data.has_more;
    appendCheckinCards(data.items);
    more.textContent = checkinState.hasMore ? "加载更多" : "没有更多了";
    more.disabled = !checkinState.hasMore;
  } catch (err) {
    more.textContent = "加载失败，点击重试";
    more.disabled = false;
  }
  checkinState.loading = false;
}

function appendCheckinCards(items) {
  const grid = document.getElementById("checkinGrid");
  for (const it of items) {
    const month = it.checkin_date.slice(0, 7);
    if (month !== checkinState.lastMonth) {
      checkinState.lastMonth = month;
      const head = document.createElement("h4");
      head.className = "checkin-month";
      head.textContent = month;
      grid.appendChild(head);
    }
    const card = document.createElement("button");
    card.type = "button";
    card.className = "checkin-card";
    card.dataset.reveal = "";
    const img = document.createElement("img");
    img.loading = "lazy";
    img.src = it.thumbnail_url || it.image_url;
    img.alt = it.checkin_date;
    const label = document.createElement("span");
    label.className = "checkin-card-date";
    label.textContent = it.checkin_date.slice(0, 16);
    card.append(img, label);
    card.addEventListener("click", () => openLightbox(it.image_url, it.id));
    grid.appendChild(card);
  }
}

function renderTabShell() {
  const tabs = document.createElement("div");
  tabs.className = "profile-tabs";
  for (const [key, label] of [
    ["titles", "称号"],
    ["checkins", "打卡记录"],
  ]) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = label;
    btn.dataset.tab = key;
    btn.className = key === activeTab ? "active" : "";
    btn.addEventListener("click", () => switchTab(key));
    tabs.appendChild(btn);
  }
  return tabs;
}
```

`renderProfile` 里从 `const titleHead = ...` 到末尾 `profileMain.appendChild(renderTitles());` 的整段（titleHead/filters/列表追加）替换为：

```js
  profileMain.appendChild(renderTabShell());

  const panelTitles = document.createElement("section");
  panelTitles.id = "panelTitles";
  panelTitles.className = "tab-panel" + (activeTab === "titles" ? "" : " hidden");

  const filters = document.createElement("div");
  filters.className = "title-filters";
  for (const [key, label] of [
    ["all", "全部"],
    ["condition", "条件"],
    ["lottery", "抽奖"],
  ]) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = label;
    btn.className = key === titleFilter ? "active" : "";
    btn.addEventListener("click", () => {
      titleFilter = key;
      filters.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const old = panelTitles.querySelector(".title-list");
      if (old) old.replaceWith(renderTitles());
    });
    filters.appendChild(btn);
  }
  panelTitles.appendChild(filters);
  panelTitles.appendChild(renderTitles());

  const panelCheckins = document.createElement("section");
  panelCheckins.id = "panelCheckins";
  panelCheckins.className = "tab-panel" + (activeTab === "checkins" ? "" : " hidden");
  const grid = document.createElement("div");
  grid.id = "checkinGrid";
  grid.className = "checkin-grid";
  const moreBtn = document.createElement("button");
  moreBtn.type = "button";
  moreBtn.id = "checkinMore";
  moreBtn.className = "checkin-more";
  moreBtn.textContent = "加载更多";
  moreBtn.addEventListener("click", loadCheckins);
  panelCheckins.append(grid, moreBtn);

  profileMain.append(panelTitles, panelCheckins);
  if (activeTab === "checkins" && !checkinState.loaded) {
    checkinState.loaded = true;
    loadCheckins();
  }
```

事件绑定区（`dayDialogClose.addEventListener` 一段附近）追加分享弹层逻辑：

```js
const shareDialog = document.getElementById("shareDialog");
const shareDialogClose = document.getElementById("shareDialogClose");
const lightboxShareBtn = document.getElementById("lightboxShare");

function openShareCard() {
  if (currentRecordId == null) return;
  const url = `/api/me/checkin/${currentRecordId}/share.png`;
  shareImg.src = url;
  const dl = document.getElementById("shareDownload");
  dl.href = url;
  shareDialog.showModal();
}

lightboxShareBtn.addEventListener("click", openShareCard);
shareDialogClose.addEventListener("click", () => shareDialog.close());
```

（`shareImg` 常量在文件顶部元素引用区一并声明：`const shareImg = document.getElementById("shareImg");`）

- [ ] **Step 4: 语法与回归验证**

Run: `node --check webapp/static/profile.js`
Expected: 无输出（语法通过）

Run: `python -m pytest test/test_webapp_api_suites.py -v`
Expected: 全部 passed（前端改动不影响 API，但确认无意外破坏）

- [ ] **Step 5: 不提交**（Task 4 统一提交）

---

### Task 4: 文档同步 + 版本 bump + 唯一 feature commit

**Files:**
- Modify: `CHANGELOG.md`（顶部新增 `[1.46.0]` 节）
- Modify: `core/config.py:17`（`BOTERO_VERSION = "1.46.0"`）
- Modify: `specs/web-gallery.md`（`/api/me` 路由表加两行）
- Commit: Task 1–4 全部文件（注：web 路由仅记于 specs/web-gallery.md，kb/OPERATIONS.md 的 API 速查是 OneBot 侧，无需改）

**Interfaces:**
- Consumes: Task 1–3 的全部产物
- Produces: 合入 master 的单一 feature commit

- [ ] **Step 1: CHANGELOG**

`# 更新日志` 说明段后、`## [1.45.2]` 之前插入：

```markdown
## [1.46.0]

- **个人中心打卡卡片 Tab 与分享卡**：个人主页「称号」区升级为「称号 / 打卡记录」并列 Tab，打卡记录按月分组、卡片式浏览全部打卡图（分页加载）；lightbox 查看打卡图新增「生成分享卡片」——服务端 PIL 合成浅色分享卡（头像/昵称/日期/照片/连击与累计统计/品牌 footer），极端宽高比（全景、超长图）自动 contain 进 1000×1250 照片区并以模糊背景铺满，成品恒定 1080 宽、总高上界 ~1700
```

- [ ] **Step 2: 版本 bump**

`core/config.py`：`BOTERO_VERSION = "1.45.2"` → `BOTERO_VERSION = "1.46.0"`

- [ ] **Step 3: specs/web-gallery.md 路由表**

`GET /api/me/day` 行后插入：

```markdown
| `GET` | `/api/me/checkins` | 必须 | 我的打卡图分页（每页 24，仅含本地文件） |
| `GET` | `/api/me/checkin/{id}/share.png` | 必须 | 打卡分享卡 PNG（仅本人记录，404=不存在/非本人/无文件） |
```

- [ ] **Step 4: 全量回归**

Run: `python -m pytest`
Expected: 全部 passed（`test_llm.py` 默认被排除）

- [ ] **Step 5: 唯一 feature commit**

```bash
git add core/gen_image/checkin_share_card.py core/db/checkin.py webapp/gallery/repository.py \
  webapp/profile/share_service.py webapp/profile/app.py \
  webapp/static/profile.html webapp/static/profile.js core/web/static/profile.css \
  test/test_checkin_share_card.py test/scripts/check_profile_checkins.py \
  CHANGELOG.md core/config.py specs/web-gallery.md
git commit -m "feat(个人中心): 打卡卡片Tab与分享卡生成"
```

（Commit-msg 钩子要求中文 Conventional Commits；>12 文件的分块提示是警告不阻断。）
