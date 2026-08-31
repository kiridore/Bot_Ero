# /rank 与 /本周板油 图片化展示实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/rank`（积分排行榜）与 `/本周板油`（周打卡成员清单）的输出从纯文本改为 Pillow 渲染的图片卡片，全员带头像，带磁盘头像缓存（下载失败回退缓存），渲染异常回退纯文本。

**Architecture:** 复用现有 `core/gen_image/` 管线（fonts/avatar_helper），新增共享渲染器 `core/gen_image/rank_card.py`（两个指令都是"标题+行+页脚"卡）。头像获取走新增的 `fetch_avatar_cached`（每次尝试下载、成功写缓存、失败读缓存兜底）。两个插件 `handle()` 尾部改为组 rows → 渲染 → 落盘 → `image("file://"+llonebot路径)` 发送，异常回退现有纯文本路径。

**Tech Stack:** Pillow（已在 requirements.txt）、requests（已装）。零新依赖。

**Spec:** 本文件即设计+计划（brainstorming 产出，用户已确认方案 B：全量头像+缓存兜底）。

## Global Constraints

- bot 进程禁止 `async`/`await`（纯同步多线程）。
- 两条数据路径常量：文件写 `context.python_data_path`（`./server_data`），发给 OneBot 的 file URL 用 `context.llonebot_data_path`（`/app/llonebot/server_data`）。用错是静默失败。
- 禁止 f-string SQL（本计划无 SQL 改动）。
- "一周" = 周一 08:00 → 次周一 08:00，用 `core.utils.get_monday_to_monday()`（week_list 现有逻辑已正确，不改）。
- **不能用 `cq.image(path, cache=False)` 防旧图**：`core/cq.py` 的 `image()` 未把 cache 写入 data dict，参数是空操作。用"唯一时间戳文件名 + 发送前清理同前缀旧文件"规避，不动协议代码。
- 测试输出/缓存：`context.python_data_path` 是硬编码 `./server_data` 模块全局，**不在** conftest 的 `BOTERO_*` 重定向范围内——所有会触达它的测试必须 `patch("core.gen_image.<模块>.context.python_data_path", <临时目录>)`（沿用 `test_save_personal_record_png_writes_file` 的既有模式），否则 pytest 写真实 `server_data/`。
- Commit 消息中文 + Conventional Commits，逻辑变更配套文件（代码+测试+CHANGELOG）进同一 commit。
- 版本 bump：新功能 minor → `1.30.0`。

## 文件结构

| 文件 | 动作 | 职责 |
|------|------|------|
| `core/gen_image/rank_card.py` | 新建 | `RankRow` 数据类 + `render_rank_card()` 渲染 + `save_rank_png()` 落盘（返回双路径） |
| `core/gen_image/avatar_helper.py` | 修改 | 追加 `fetch_avatar_cached()`：下载+缓存+兜底 |
| `core/gen_image/__init__.py` | 修改 | 导出新符号 |
| `plugins/leaderboard/__init__.py` | 修改 | handle() 图片化 + 文本回退 |
| `plugins/week_list/__init__.py` | 修改 | handle() 图片化 + 文本回退 + 修名片取值 KeyError 隐患 |
| `test/test_gen_image.py` | 修改 | 追加 rank_card 渲染与头像缓存的测试类 |
| `CHANGELOG.md` + `core/config.py` | 修改 | `[1.30.0]` 节 + bump |

---

### Task 1: 头像缓存获取器 `fetch_avatar_cached`

**Files:**
- Modify: `core/gen_image/avatar_helper.py`
- Modify: `core/gen_image/__init__.py`
- Test: `test/test_gen_image.py`（追加测试类）

**Interfaces:**
- Consumes: `core.api` 的 `api.get_qq_avatar(user_id) -> str`（已有）；`context.python_data_path`
- Produces: `fetch_avatar_cached(api, user_id) -> PIL.Image.Image | None`——api 只需有 `get_qq_avatar` 方法（鸭子类型，便于测试用 stub）

- [ ] **Step 1: 写失败测试**

在 `test/test_gen_image.py` 末尾追加（沿用文件顶部已有的 `PILImage` 守卫约定；`GEN_IMAGE_OUTPUT`、`_assert_png_file` 模式）：

```python
class TestFetchAvatarCachedLogic(unittest.TestCase):
    """不依赖网络与真实 server_data：patch 下载源与缓存目录。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="avatar_cache_test_")
        self.addCleanup(self._tmp.cleanup)
        self.cache_root = Path(self._tmp.name)

    def _avatar_bytes(self, color=(200, 30, 30), size=(64, 48)):
        im = PILImage.new("RGB", size, color)
        buf = BytesIO()
        im.save(buf, format="PNG")
        return buf.getvalue()

    def _write_source(self, data: bytes) -> str:
        src = self.cache_root / "avatar_src.png"
        src.write_bytes(data)
        return str(src)

    def _patch_cache(self):
        from core.gen_image import avatar_helper
        return patch.object(avatar_helper.context, "python_data_path", self._tmp.name)

    def test_download_success_writes_cache(self):
        from core.gen_image.avatar_helper import fetch_avatar_cached

        payload = self._avatar_bytes()
        url = "file://" + self._write_source(payload)  # 本地文件当下载源

        class _Api:
            def get_qq_avatar(self, user_id):
                return url

        with self._patch_cache():
            im = fetch_avatar_cached(_Api(), 987001)
        self.assertIsNotNone(im)
        cache = self.cache_root / "avatar_cache" / "987001.png"
        self.assertTrue(cache.is_file())
        with PILImage.open(cache) as loaded:
            self.assertEqual(loaded.size, (64, 48))

    def test_download_failure_falls_back_to_cache(self):
        from core.gen_image.avatar_helper import fetch_avatar_cached

        cache = self.cache_root / "avatar_cache" / "987002.png"
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(self._avatar_bytes((30, 200, 30)))

        class _Api:
            def get_qq_avatar(self, user_id):
                return ""  # 模拟 API 失败

        with self._patch_cache():
            im = fetch_avatar_cached(_Api(), 987002)
        self.assertIsNotNone(im)
        with PILImage.open(im) as loaded:
            self.assertEqual(loaded.size, (64, 48))

    def test_total_failure_returns_none(self):
        from core.gen_image.avatar_helper import fetch_avatar_cached

        class _Api:
            def get_qq_avatar(self, user_id):
                raise RuntimeError("api down")

        with self._patch_cache():
            self.assertIsNone(fetch_avatar_cached(_Api(), 987003))
```

注意：`test/test_gen_image.py` 现有 import 段需要补 `from io import BytesIO`、`import tempfile`、`from unittest.mock import patch`（`Path`/`PILImage` 已有；已有则跳过）。`requests.get` 对 `file://` URL 的支持：requests 不处理 file:// 协议——实现里对 `file://` 前缀做本地读取分支（仅测试受益，约 3 行），生产 URL 是 http(s) 不受影响。

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest test/test_gen_image.py -k FetchAvatarCached -v`
Expected: FAIL（`ImportError: cannot import name 'fetch_avatar_cached'`）。测试类无 `@skipUnless` 守卫（不依赖 Pillow 安装与否的网络逻辑测试外的渲染断言——类内用到 PILImage 构图，仍需 Pillow；给类加上与文件既有风格一致的 `@unittest.skipUnless(PILImage is not None, ...)` 装饰器）。

- [ ] **Step 3: 实现**

`core/gen_image/avatar_helper.py` 顶部补 import（`from io import BytesIO`、`from pathlib import Path`、`import requests`、`from core import context`），文件末尾追加：

```python
def fetch_avatar_cached(api, user_id) -> Image.Image | None:
    """尝试下载最新头像；成功则写入磁盘缓存，任何失败回退读缓存，再失败返回 None。"""
    cache_path = Path(context.python_data_path) / "avatar_cache" / f"{user_id}.png"
    url = ""
    try:
        url = api.get_qq_avatar(user_id) or ""
    except Exception:
        url = ""
    if url:
        try:
            if url.startswith("file://"):  # 测试用本地文件源；生产为 http(s)
                r = None
                content = Path(url.removeprefix("file://")).read_bytes()
            else:
                r = requests.get(url, timeout=8)
                r.raise_for_status()
                content = r.content
            im = Image.open(BytesIO(content))
            im.load()
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            im.convert("RGB").save(cache_path, format="PNG")
            return im
        except Exception:
            pass
    try:
        if cache_path.is_file():
            return Image.open(cache_path)
    except Exception:
        pass
    return None
```

`core/gen_image/__init__.py` 补导出：

```python
from core.gen_image.avatar_helper import fetch_avatar_cached
```

并加入 `__all__`。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest test/test_gen_image.py -v`
Expected: 全部 PASS（含原有用例）

- [ ] **Step 5: Commit**

```bash
git add core/gen_image/avatar_helper.py core/gen_image/__init__.py test/test_gen_image.py
git commit -m "feat(图片): 新增头像下载缓存与失败兜底 fetch_avatar_cached"
```

---

### Task 2: 共享渲染器 `rank_card.py`

**Files:**
- Create: `core/gen_image/rank_card.py`
- Modify: `core/gen_image/__init__.py`
- Test: `test/test_gen_image.py`（追加测试类）

**Interfaces:**
- Consumes: `core.gen_image.fonts.load_font/text_width/truncate_text`、`core.gen_image.avatar_helper.raster_circle_avatar_on_rgb`、`context`
- Produces:
  - `RankRow(rank: int, name: str, detail: str, avatar: PIL.Image.Image | None = None)`（frozen dataclass）
  - `render_rank_card(title: str, subtitle: str, rows: list[RankRow], footer: str = FOOTER_TEXT) -> PIL.Image.Image`（RGB，固定宽 620，高自适应）
  - `save_rank_png(kind: str, img) -> tuple[str, str]`：写入 `{python_data_path}/rank_cards/{kind}_{毫秒时间戳}.png`，清理同 kind 旧文件，返回 `(python侧绝对路径, "{llonebot_data_path}/rank_cards/{文件名}")`

- [ ] **Step 1: 写失败测试**

`test/test_gen_image.py` 追加：

```python
@unittest.skipUnless(PILImage is not None, "需要安装 Pillow（pip install pillow）")
class TestRankCard(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="rank_card_test_")
        self.addCleanup(self._tmp.cleanup)
        self.out_root = Path(self._tmp.name)

    def _assert_png_file(self, path: Path) -> None:
        self.assertTrue(path.is_file(), f"未生成文件: {path}")
        self.assertGreater(path.stat().st_size, 100, f"文件过小: {path}")
        with PILImage.open(path) as loaded:
            self.assertEqual(loaded.format, "PNG")

    def _render_basic(self):
        from core.gen_image.rank_card import RankRow, render_rank_card

        rows = [
            RankRow(rank=1, name="「画师」阿囡", detail="114514分",
                    avatar=PILImage.new("RGB", (96, 96), (212, 175, 55))),
            RankRow(rank=2, name="板油二号", detail="1919分", avatar=None),
            RankRow(rank=3, name="很长的名字" * 8, detail="810分", avatar=None),
        ]
        return render_rank_card("积分排行榜", "TOP 3", rows)

    def test_render_basic(self):
        img = self._render_basic()
        self.assertEqual(img.mode, "RGB")
        self.assertEqual(img.width, 620)
        self.assertGreater(img.height, 300)
        path = GEN_IMAGE_OUTPUT / "rank_card_basic.png"
        img.save(path, format="PNG")
        self._assert_png_file(path)

    def test_render_week_board_many_rows(self):
        from core.gen_image.rank_card import RankRow, render_rank_card

        rows = [
            RankRow(rank=i, name=f"板油{i:02d}", detail=f"2026-08-{(i % 28) + 1:02d} 09:12:34")
            for i in range(1, 31)
        ]
        img = render_rank_card("本周打卡板油", "2026-08-31 ~ 2026-09-07 · 共 30 名板油完成打卡", rows)
        self.assertGreater(img.height, 1000)  # 30 行 + 头像行的最小高度保障
        path = GEN_IMAGE_OUTPUT / "rank_card_week_board.png"
        img.save(path, format="PNG")
        self._assert_png_file(path)

    def test_save_rank_png_rotates_files(self):
        from core.gen_image import rank_card as rank_card_module
        from core.gen_image.rank_card import save_rank_png

        with patch.object(rank_card_module.context, "python_data_path", self._tmp.name):
            img = self._render_basic()
            py1, send1 = save_rank_png("points_rank", img)
            img2 = render_rank_card(
                "标题", "副标题",
                [RankRow(rank=1, name="乙", detail="2分")],
            )
            py2, send2 = save_rank_png("points_rank", img2)

        self.assertFalse(Path(py1).is_file())  # 旧图已被清理
        self.assertTrue(Path(py2).is_file())
        self.assertNotEqual(py1, py2)
        self.assertIn("rank_cards", send2)
        self.assertIn("points_rank_", Path(py2).name)
```

（`render_rank_card` / `RankRow` 在本测试方法顶部补 `from core.gen_image.rank_card import RankRow, render_rank_card` 后可直接用。）

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest test/test_gen_image.py -k RankCard -v`
Expected: FAIL（`ModuleNotFoundError: core.gen_image.rank_card`）

- [ ] **Step 3: 实现 `core/gen_image/rank_card.py`**

```python
from __future__ import annotations

import glob
import os
import time
from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageDraw

from core import context
from core.gen_image.avatar_helper import raster_circle_avatar_on_rgb
from core.gen_image.fonts import load_font, text_width, truncate_text

CARD_BG = (245, 245, 245)
TEXT_MAIN = (45, 45, 45)
TEXT_DIM = (110, 110, 110)
TEXT_VALUE = (55, 55, 55)
SEPARATOR = (225, 225, 225)
AVATAR_PLACEHOLDER = (215, 215, 215)

CARD_WIDTH = 620
H_PAD = 28
V_PAD_TOP = 24
TITLE_SIZE = 22
SUBTITLE_SIZE = 14
SUBTITLE_GAP = 6
LIST_TOP_GAP = 18
ROW_GAP = 10
AVATAR_SIZE = 40
RANK_COL_W = 36
ROW_TEXT_GAP = 12
RANK_SIZE = 16
NAME_SIZE = 16
DETAIL_SIZE = 14
FOOTER_SIZE = 12
FOOTER_TEXT = "Power by 小埃同学"
FOOTER_PAD_TOP = 16
FOOTER_PAD_BOTTOM = 14
# 前三名奖牌色：金银铜，其余主文字色
MEDAL_COLORS = {1: (196, 154, 34), 2: (130, 130, 134), 3: (176, 115, 57)}


@dataclass(frozen=True)
class RankRow:
    rank: int
    name: str
    detail: str
    avatar: Optional[Image.Image] = None


def _line_height(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def render_rank_card(
    title: str,
    subtitle: str,
    rows: list[RankRow],
    footer: str = FOOTER_TEXT,
) -> Image.Image:
    """标题 + 副标题 + 若干行（排名/头像/名称/右侧 detail）+ 页脚的自适应竖卡。"""
    font_title = load_font(TITLE_SIZE)
    font_subtitle = load_font(SUBTITLE_SIZE)
    font_rank = load_font(RANK_SIZE)
    font_name = load_font(NAME_SIZE)
    font_detail = load_font(DETAIL_SIZE)
    font_footer = load_font(FOOTER_SIZE)

    probe = Image.new("RGB", (1, 1), CARD_BG)
    draw_probe = ImageDraw.Draw(probe)

    title_h = _line_height(draw_probe, title, font_title)
    subtitle_h = _line_height(draw_probe, subtitle, font_subtitle) if subtitle else 0
    row_h = max(AVATAR_SIZE, _line_height(draw_probe, "样", font_name))
    footer_h = _line_height(draw_probe, footer, font_footer)

    content_w = CARD_WIDTH - H_PAD * 2
    body_height = 0
    if rows:
        body_height = len(rows) * row_h + (len(rows) - 1) * ROW_GAP

    height = (
        V_PAD_TOP + title_h + SUBTITLE_GAP + subtitle_h + LIST_TOP_GAP
        + body_height + FOOTER_PAD_TOP + footer_h + FOOTER_PAD_BOTTOM
    )

    img = Image.new("RGB", (CARD_WIDTH, int(height)), CARD_BG)
    draw = ImageDraw.Draw(img)

    y = V_PAD_TOP
    draw.text((H_PAD, y), title, font=font_title, fill=TEXT_MAIN)
    y += title_h + SUBTITLE_GAP
    if subtitle:
        draw.text((H_PAD, y), subtitle, font=font_subtitle, fill=TEXT_DIM)
    y += subtitle_h + LIST_TOP_GAP

    for i, row in enumerate(rows):
        cy = y + row_h / 2  # 行垂直中线
        x = H_PAD
        # 排名列（右对齐数字，前三奖牌色）
        rank_str = str(row.rank)
        rank_w = text_width(draw, rank_str, font_rank)
        rank_color = MEDAL_COLORS.get(row.rank, TEXT_VALUE)
        draw.text((x + RANK_COL_W - rank_w, cy - _line_height(draw, rank_str, font_rank) / 2),
                  rank_str, font=font_rank, fill=rank_color)
        x += RANK_COL_W + ROW_TEXT_GAP
        # 头像（无则灰圆占位）
        if row.avatar is not None:
            avatar_im = raster_circle_avatar_on_rgb(row.avatar, AVATAR_SIZE, background=CARD_BG)
            img.paste(avatar_im, (int(x), int(cy - AVATAR_SIZE / 2)))
        else:
            draw.ellipse(
                (x, cy - AVATAR_SIZE / 2, x + AVATAR_SIZE, cy + AVATAR_SIZE),
                fill=AVATAR_PLACEHOLDER,
            )
        x += AVATAR_SIZE + ROW_TEXT_GAP
        # detail 右对齐，name 在剩余宽度内截断
        detail_w = text_width(draw, row.detail, font_detail)
        draw.text((CARD_WIDTH - H_PAD - detail_w, cy - _line_height(draw, row.detail, font_detail) / 2),
                  row.detail, font=font_detail, fill=TEXT_DIM)
        name_max = content_w - RANK_COL_W - ROW_TEXT_GAP - AVATAR_SIZE - ROW_TEXT_GAP - detail_w - 8
        name_str = truncate_text(draw, row.name, font_name, max(60, name_max))
        draw.text((x, cy - _line_height(draw, name_str, font_name) / 2),
                  name_str, font=font_name, fill=TEXT_MAIN)
        y += row_h
        if i < len(rows) - 1:
            draw.line((H_PAD, y + ROW_GAP / 2, CARD_WIDTH - H_PAD, y + ROW_GAP / 2),
                      fill=SEPARATOR, width=1)
            y += ROW_GAP

    footer_w = text_width(draw, footer, font_footer)
    draw.text(((CARD_WIDTH - footer_w) / 2, height - FOOTER_PAD_BOTTOM - footer_h),
              footer, font=font_footer, fill=TEXT_DIM)
    return img


def save_rank_png(kind: str, image_obj: Image.Image) -> tuple[str, str]:
    """写入时间戳唯一文件并清理同 kind 旧图；返回 (python 侧路径, OneBot 发送用路径)。

    文件名必须唯一：cq.image() 的 cache 参数是空操作，固定名会被 QQ 端按文件名缓存旧图。
    """
    out_dir = f"{context.python_data_path}/rank_cards"
    os.makedirs(out_dir, exist_ok=True)
    for old in glob.glob(f"{out_dir}/{kind}_*.png"):
        try:
            os.remove(old)
        except OSError:
            pass
    fname = f"{kind}_{int(time.time() * 1000)}.png"
    path = f"{out_dir}/{fname}"
    image_obj.save(path)
    return path, f"{context.llonebot_data_path}/rank_cards/{fname}"
```

`core/gen_image/__init__.py` 追加导出：

```python
from core.gen_image.rank_card import RankRow, render_rank_card, save_rank_png
```

并加入 `__all__`。

- [ ] **Step 4: 跑测试确认通过 + 人工看图**

Run: `python -m pytest test/test_gen_image.py -v`
Expected: 全部 PASS

Run: `ls test/gen_image_output/rank_card_*.png`——打开肉眼检查排版（中文不缺字、奖牌色、头像圆裁剪、detail 右对齐、30 行长卡不溢出）。中文渲染异常通常是字体回退问题，回到 `fonts.load_font` 检查候选路径。

- [ ] **Step 5: Commit**

```bash
git add core/gen_image/rank_card.py core/gen_image/__init__.py test/test_gen_image.py
git commit -m "feat(图片): 新增榜单卡片渲染器 rank_card（排名/头像/自适应高度）"
```

---

### Task 3: `/rank`（leaderboard 插件）图片化

**Files:**
- Modify: `plugins/leaderboard/__init__.py`

**Interfaces:**
- Consumes: Task 1 `fetch_avatar_cached`、Task 2 `RankRow/render_rank_card/save_rank_png`；`core.cq.image`；`context.llonebot_data_path`
- Produces: 无（终端插件改动）

- [ ] **Step 1: 改写 handle()**

保留现有空数据守卫与名片/称号获取逻辑，把"组 lines → 发文本"改为"组 entries → 尝试图片 → 异常回退文本"。完整新 `handle()`：

```python
def handle(self):
    group_id = self.bot_event.group_id
    if not group_id:
        self.api.send_msg(text("请在群里使用 /排名 或 /rank"))
        return

    top_rows = self.dbmanager.points.leaderboard(limit=10)
    if len(top_rows) == 0:
        self.api.send_msg(text("当前还没有积分数据喵~"))
        return

    entries = []  # (排名, user_id, 展示名, 积分)
    for index, (user_id, points) in enumerate(top_rows, start=1):
        member_name = str(user_id)
        try:
            member = self.api.get_group_member_info(int(user_id))
            member_name = member.get("card") or member.get("nickname") or str(user_id)
        except Exception:
            member_name = str(user_id)
        title_prefix = self._format_title_prefix(user_id)
        if title_prefix:
            member_name = f"{title_prefix}{member_name}"
        entries.append((index, user_id, member_name, points))

    try:
        from core.gen_image import RankRow, render_rank_card, save_rank_png, fetch_avatar_cached
        rows = [
            RankRow(
                rank=rank,
                name=name,
                detail=f"{points}分",
                avatar=fetch_avatar_cached(self.api, int(user_id)),
            )
            for rank, user_id, name, points in entries
        ]
        img = render_rank_card("积分排行榜", f"TOP {len(rows)}", rows)
        _, send_path = save_rank_png("points_rank", img)
        self.api.send_msg(image("file://" + send_path))
    except Exception:
        logger.exception("积分排行榜图片生成失败，回退纯文本")
        lines = [f"{rank}. {name} - {points}分" for rank, _, name, points in entries]
        self.api.send_msg(text("积分排行榜 TOP10\n" + "\n".join(lines)))
```

import 段调整（模块顶部，与 personal_records 风格一致，**不要**函数内 import）：`from core.cq import text` → `from core.cq import image, text`；补 `from core.logger import logger`；补 `from core.gen_image import RankRow, fetch_avatar_cached, render_rank_card, save_rank_png`。代码块中 try 内那行 `from core.gen_image import ...` 相应删除。

注意：`fetch_avatar_cached` 对每个失败头像返回 None（渲染器画灰圆占位），单点失败不影响整卡。

- [ ] **Step 2: 全量回归 + 语法自检**

Run: `python -m pytest test/ -x -q`
Expected: 全部 PASS

Run: `python -c "import plugins.leaderboard"`（确认插件模块可导入）

- [ ] **Step 3: Commit**

```bash
git add plugins/leaderboard/__init__.py
git commit -m "feat(排行): /rank 积分排行榜改为图片卡片展示，失败回退纯文本"
```

---

### Task 4: `/本周板油`（week_list 插件）图片化

**Files:**
- Modify: `plugins/week_list/__init__.py`

**Interfaces:**
- Consumes: 同 Task 3
- Produces: 无

- [ ] **Step 1: 改写 handle()**

空周守卫保留纯文本。顺手修掉 `group_member_info["card"]` 裸键访问（API 失败返回 `{}` 时 KeyError 会炸整条指令——图片路径同样依赖这段取名片，属必须的根因修复，对齐 leaderboard 的 `.get` 写法）。完整新 `handle()`：

```python
def handle(self):
    start_date, end_date = get_monday_to_monday()
    checkin_users = self.dbmanager.checkin.search_range(start_date, end_date)
    if len(checkin_users) <= 0:
        self.api.send_msg(text("本周({}-{})竟然还没有板油完成打卡".format(start_date, end_date)))
        return

    user_map = {}
    logger.debug(checkin_users)
    # [(id, user_id, '2025-08-12 01:22:56', 'EDE6A7...png')]
    for user_info in checkin_users:
        user_map[user_info[1]] = user_info[2]

    entries = []  # (序号, user_id, 展示名, 打卡时间)
    for user_id, checkin_time in user_map.items():
        member_name = str(user_id)
        try:
            info = self.api.get_group_member_info(user_id)
            member_name = info.get("card") or info.get("nickname") or str(user_id)
        except Exception:
            member_name = str(user_id)
        title_prefix = self._format_title_prefix(user_id)
        if title_prefix:
            member_name = f"{title_prefix}{member_name}"
        entries.append((len(entries) + 1, user_id, member_name, checkin_time))

    try:
        rows = [
            RankRow(
                rank=rank,
                name=name,
                detail=str(checkin_time),
                avatar=fetch_avatar_cached(self.api, int(user_id)),
            )
            for rank, user_id, name, checkin_time in entries
        ]
        subtitle = "本周({} ~ {}) 共 {} 名板油完成了打卡".format(start_date, end_date, len(entries))
        img = render_rank_card("本周打卡板油", subtitle, rows)
        _, send_path = save_rank_png("week_board", img)
        self.api.send_msg(image("file://" + send_path))
    except Exception:
        logger.exception("本周板油图片生成失败，回退纯文本")
        display_str = "".join("- {}, {}\n".format(name, checkin_time)
                              for _, _, name, checkin_time in entries)
        self.api.send_msg(text(
            "本周({}-{})\n- 共有{}名板油完成了打卡:\n{}".format(
                start_date, end_date, len(entries), display_str)
        ))
```

import 段调整：`from core.cq import text` → `from core.cq import image, text`；顶部补
`from core.gen_image import RankRow, fetch_avatar_cached, render_rank_card, save_rank_png`。

- [ ] **Step 2: 全量回归 + 语法自检**

Run: `python -m pytest test/ -x -q`
Expected: 全部 PASS

Run: `python -c "import plugins.week_list"`

- [ ] **Step 3: Commit**

```bash
git add plugins/week_list/__init__.py
git commit -m "feat(打卡): /本周板油 改为图片卡片展示，失败回退纯文本并修复名片取值隐患"
```

---

### Task 5: CHANGELOG + 版本 bump + 真机验证清单

**Files:**
- Modify: `core/config.py`（`BOTERO_VERSION = "1.29.1"` → `"1.30.0"`）
- Modify: `CHANGELOG.md`（`## [未发布]` 与 `## [1.29.1]` 之间插入新节）

- [ ] **Step 1: 更新 CHANGELOG 与版本号**

```markdown
## [1.30.0] - 2026-08-31

### 新增

- **排行榜与周打卡板油图片化**：`/排名`（`/rank`）与 `/本周板油` 指令输出改为图片卡片——含排名奖牌配色、成员圆形头像与称号展示；头像首次下载后写入本地缓存，后续下载失败自动回退缓存头像；图片渲染异常时回退原纯文本输出，不影响使用
```

`core/config.py`: `BOTERO_VERSION = "1.30.0"`

- [ ] **Step 2: 全量回归**

Run: `python -m pytest -q`
Expected: 全部 PASS

- [ ] **Step 3: Commit**

```bash
git add core/config.py CHANGELOG.md
git commit -m "feat(版本): 1.30.0 /rank 与 /本周板油 图片化展示"
```

- [ ] **Step 4: 真机验证（部署后人工执行，不在本计划自动化范围）**

群里依次发 `/rank` 与 `/本周板油`，检查：图片正常出图、头像正确、称号前缀在、无旧图缓存串图问题；断网/杀 OneBot 场景观察是否回退纯文本。首次触发后确认 `server_data/avatar_cache/` 与 `server_data/rank_cards/` 生成。

## Self-Review 记录

- 规格覆盖：方案 B（全量头像）→ Task 3/4 全员 `fetch_avatar_cached`；缓存兜底 → Task 1；纯文本回退 → Task 3/4 except 分支；防旧图 → Task 2 唯一文件名+清理。✓
- 占位符扫描：无 TBD/TODO；所有代码步骤给出完整代码。✓
- 类型一致性：`RankRow(rank, name, detail, avatar)` 在 Task 2 定义、Task 3/4 消费一致；`save_rank_png -> tuple[str, str]` 两处均解包 `_, send_path`。✓
