# 打卡隐私与时间线可见性 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打卡内容在时间线上获得两级隐私控制——私聊打卡可对他人隐藏（作者仍可见并带角标）、打卡图片可对他人高斯模糊（作者看原图）；QQ 私聊与网页端打卡统一打"私聊"标记上传时间线。

**Architecture:** 设置沿用 `core/user_settings.py` JSON 存储（每用户一键值，不新增表）；私聊标记双落点——`checkin_records.is_private` 列（DB）+ 时间线事件 `data.private` 字段（协议已有 data JSON，timeline_events 不加列）；可见性与模糊全部在**读侧**（webapp/timeline 序列化时）按"作者设置 × 事件标记 × 查看者身份"动态计算，历史事件无标记即视为公开，天然满足"历史不动"。模糊图服务端生成（Pillow 对缩略图高斯模糊，独立缓存文件），前端只认 URL。

**Tech Stack:** 纯同步 bot（禁 async）；FastAPI webapp；Pillow（已在 requirements）；pytest + node 最小 DOM stub。

**Spec:** specs/timeline-protocol.md（时间线协议权威，动协议代码前先读）；specs/web-gallery.md；kb/DATABASE.md。

## 需求裁定记录（用户已确认）

1. 私聊打卡 = QQ 私聊发 `/打卡`（生产插件对私聊全开放，框架不改）。
2. 设置存 JSON（`core/user_settings.py`），**不新增数据库表**。
3. 新设置项：①私聊打卡是否显示在时间线；②时间线打卡图片仅自己可见（他人看高斯模糊版）。
4. 隐藏语义：作者关闭后**他人完全看不到**该打卡事件；**作者自己仍可见**，卡片角落标注「仅自己可见」。
5. 历史数据不修改，仅管未来（旧 checkin_records 行 is_private 默认 0；旧时间线事件无 data.private → 永远按公开处理）。
6. 网页端打卡本次起也上传时间线，并打私聊标记。

## 计划内假设（默认值与范围，可 veto）

- **A1** 两个开关默认值 = True（维持现状：私聊打卡默认上时间线、图片默认对他人清晰）。
- **A2** 图片模糊设置作用于作者的**全部**打卡事件图（QQ 群聊/私聊/网页）。
- **A3** 角标仅出现在"被隐藏的私聊打卡 × 作者本人查看"场景；模糊场景不加角标（模糊本身即视觉信号）。
- **A4** 图库页 `/gallery` 不受模糊设置影响（仅时间线生效）。

## Global Constraints

- bot 进程（plugins/、core/）禁止 async/await；webapp 路由 async 合法但本计划新代码走同步 def（读 JSON/DB 均同步）。
- SQL 一律 `?` 参数化；新列迁移放 `core/db/_base.py`（照 message_id 迁移模式：PRAGMA table_info 探测 + ALTER）。
- 文档同 commit：Task 1 带 kb/DATABASE.md + specs/database.md + specs/timeline-protocol.md；Task 4 带 specs/web-gallery.md。
- 版本：整分支为一个 minor 功能，最终 commit 统一 bump `BOTERO_VERSION` 至 **1.25.0** + CHANGELOG `[1.25.0]` 节（中间任务不 bump，分支合并即完整功能——避免 4 个中间版本号）。
- 测试不触真实 data.db/server_data：进程内测试用 /tmp DB + monkeypatch；子进程脚本套件自建临时库（照 test/scripts/check_*.py 模式）。
- Commit 中文 Conventional Commits。

---

### Task 1: 私聊标记落库与事件标记（bot 侧）

**Files:**
- Modify: `core/db/_base.py`（checkin_records 迁移块，约 :192-196）
- Modify: `core/db/checkin.py`（`insert`，约 :7-16）
- Modify: `plugins/checkin/__init__.py`（handle 内 insert + emit_event，约 :41-80）
- Test: 新建 `test/test_checkin_privacy.py`
- Docs 同 commit: `kb/DATABASE.md`、`specs/database.md`、`specs/timeline-protocol.md`

**Interfaces:**
- Produces: `CheckinManager.insert(user_id, images, message_id=None, is_private=False)`（新参带默认，既有调用零改动）；时间线事件 `data: {"images": [...], "private": <bool>}`。
- 下游消费：Task 3（web 打卡 is_private=True + data.private=True）、Task 4（读侧按 data.private 过滤）。

- [ ] **Step 1: 写失败测试** — 新建 `test/test_checkin_privacy.py`：

```python
"""打卡私聊标记回归：私聊/群聊写入 is_private 列，事件 data 带 private 标记。
运行: pytest test/test_checkin_privacy.py
"""
import os
import sys
import sqlite3
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import test.helper  # noqa: F401

from core.event import Event
from core.db._base import init_schema
from core.db.checkin import CheckinManager
from plugins.checkin import CheckinPlugin
from test.helper import MockApiWrapper, make_group_message, make_private_message

DB_PATH = "/tmp/test_checkin_privacy.db"


def _last_text(plugin):
    assert plugin.api.sent_messages, "无消息发送"
    return "".join(seg["data"].get("text", "") for seg in plugin.api.sent_messages[-1][1]
                   if seg["type"] == "text")


class TestCheckinPrivateFlag(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        self.conn = sqlite3.connect(DB_PATH)
        init_schema(self.conn, self.conn.cursor())
        self.db = type("Db", (), {"checkin": CheckinManager(self.conn)})()
        self._emitted = []
        import plugins.checkin as m
        self._orig_emit = m.emit_event
        m.emit_event = lambda **kw: self._emitted.append(kw)

    def tearDown(self):
        import plugins.checkin as m
        m.emit_event = self._orig_emit
        self.conn.close()

    def _run(self, raw):
        plugin = CheckinPlugin.__new__(CheckinPlugin)
        plugin.bot_event = Event(raw)
        plugin.api = MockApiWrapper(raw)
        plugin.dbmanager = self.db
        plugin.match("message")
        plugin.handle()
        return plugin

    def _flag(self, user_id):
        return self.conn.execute(
            "SELECT is_private FROM checkin_records WHERE user_id = ?", (user_id,)
        ).fetchone()[0]

    def test_private_checkin_flagged(self):
        self._run(make_private_message("/打卡", user_id=111))
        self.assertEqual(self._flag(111), 1)
        self.assertTrue(self._emitted[-1]["data"]["private"])

    def test_group_checkin_not_flagged(self):
        self._run(make_group_message("/打卡", user_id=222))
        self.assertEqual(self._flag(222), 0)
        self.assertFalse(self._emitted[-1]["data"]["private"])


if __name__ == "__main__":
    unittest.main()
```

（若 `/打卡` handle 对图片为空仍走打卡流程——需读 handle 前段确认：无图片时 `img_list` 为空是否照样 insert——按实际行为调 raw 消息构造，测试意图不变：两种消息各触发一次完整 handle 并断言列值与事件标记。）

- [ ] **Step 2: 跑 RED** — `python -m pytest test/test_checkin_privacy.py -v`
  Expected: FAIL（OperationalError: no such column: is_private / insert 无该参）。
- [ ] **Step 3: 实现**

`core/db/_base.py` 迁移块（照 message_id 模式追加）：
```python
    cur.execute("PRAGMA table_info(checkin_records)")
    cols = {row[1] for row in cur.fetchall()}
    if "message_id" not in cols:
        cur.execute("ALTER TABLE checkin_records ADD COLUMN message_id INTEGER")
    if "is_private" not in cols:
        cur.execute("ALTER TABLE checkin_records ADD COLUMN is_private INTEGER DEFAULT 0")
```
（若现有 message_id 迁移写法不同，以其真实写法为准，平行追加 is_private 分支。）

`core/db/checkin.py insert`：
```python
    def insert(self, user_id, images, message_id=None, is_private=False):
        today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for img in images:
            self.cur.execute(
                "INSERT INTO checkin_records (user_id, checkin_date, content, message_id, is_private) VALUES (?, ?, ?, ?, ?)",
                (user_id, today_str, img, message_id, 1 if is_private else 0)
            )
        self.conn.commit()
```

`plugins/checkin/__init__.py` handle：
```python
            # 前
            msg_id = self.bot_event.message_id
            self.dbmanager.checkin.insert(self.bot_event.user_id, img_list, msg_id)
            # 后
            msg_id = self.bot_event.message_id
            is_private = self.bot_event.group_id is None  # 私聊打卡：落库 + 时间线事件双标记
            self.dbmanager.checkin.insert(self.bot_event.user_id, img_list, msg_id, is_private=is_private)
```
emit_event 调用处 data 增补：
```python
                data={"images": [...既有图片 URL 列表...], "private": is_private},
```

- [ ] **Step 4: 跑 GREEN + 回归** — `python -m pytest test/test_checkin_privacy.py test/test_plugin_tools.py -v`（含相邻套件），Expected PASS。
- [ ] **Step 5: 文档同 commit**
  - `kb/DATABASE.md` + `specs/database.md`：checkin_records 表补 `is_private INTEGER DEFAULT 0`（1=私聊打卡，0=群聊/补卡/网页历史；网页打卡 Task 3 起也写 1）。
  - `specs/timeline-protocol.md`：data 字段补充约定 `checkin 事件 data.private: bool——true=私聊/网页打卡`。
- [ ] **Step 6: Commit** — `fix(打卡): 私聊打卡落库私聊标记并在时间线事件携带private字段`

---

### Task 2: 设置键与设置页开关

**Files:**
- Modify: `core/user_settings.py`（新增两个 helper + 键约定文档）
- Modify: `webapp/static/settings.html`、`webapp/static/settings.js`（两个开关）
- Test: 新建 `test/test_user_settings_privacy.py`、`test/test_settings_render.js`

**Interfaces:**
- Produces: `user_settings.private_checkin_public(user_id) -> bool`（默认 True）；`user_settings.checkin_image_public(user_id) -> bool`（默认 True）。JSON 键：`privacy.private_checkin_public` / `privacy.checkin_image_public`。
- 下游消费：Task 4 读侧过滤；settings 页 PUT 透传（SettingsIn.privacy: dict 已支持任意键）。

- [ ] **Step 1: 写失败测试**

`test/test_user_settings_privacy.py`：
```python
"""新设置键默认值与读写回归。运行: pytest test/test_user_settings_privacy.py"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import user_settings as us


class TestPrivacyKeys(unittest.TestCase):
    def setUp(self):
        us.SETTINGS_ROOT = Path("/tmp/test_settings_keys")
        import shutil
        shutil.rmtree(us.SETTINGS_ROOT, ignore_errors=True)

    def test_defaults_true(self):
        self.assertTrue(us.private_checkin_public("333"))
        self.assertTrue(us.checkin_image_public("333"))

    def test_toggle_roundtrip(self):
        us.update_settings("333", {"privacy": {"private_checkin_public": False}})
        self.assertFalse(us.private_checkin_public("333"))
        self.assertTrue(us.checkin_image_public("333"))


if __name__ == "__main__":
    unittest.main()
```

`test/test_settings_render.js`（照 test_nav_render.js 等最小 DOM stub 模式，加载 settings.js，stub 登录态与 fetch `/api/me/settings` 返回空 privacy，断言两个开关渲染且默认勾选；返回 `{"privacy": {"private_checkin_public": false}}` 时断言对应开关未勾选）。

- [ ] **Step 2: 跑 RED** — 两个测试分别 FAIL（AttributeError / 开关不存在）。
- [ ] **Step 3: 实现**

`core/user_settings.py` 末尾（照 `privacy_public` 模式）+ 顶部键约定注释补两行：
```python
def private_checkin_public(user_id) -> bool:
    """私聊打卡是否展示在时间线（对他人）。缺省 True。"""
    return bool(get_settings(user_id).get("privacy", {}).get("private_checkin_public", True))


def checkin_image_public(user_id) -> bool:
    """时间线打卡图片是否对他人清晰可见（False=高斯模糊）。缺省 True。"""
    return bool(get_settings(user_id).get("privacy", {}).get("checkin_image_public", True))
```

`settings.html`：在现有 privacy 区块（char_public 开关旁）加两个 checkbox 行（沿用现有开关结构与文案风格）：
- 「私聊打卡显示在时间线上」`id="optPrivateCheckinPublic"`
- 「打卡图片对他人清晰可见（关闭后他人看到模糊图）」`id="optCheckinImagePublic"`

`settings.js`：加载时 `checked = !(privacy.private_checkin_public === false)`（缺省 True）；保存时把两个键并入 PUT 的 `privacy` 对象（仅当与缺省不同也照发，透传即可）。
- [ ] **Step 4: 跑 GREEN + 回归** — 两个新测试 + `python -m pytest test/test_user_settings.py -v`。
- [ ] **Step 5: Commit** — `feat(设置): 新增私聊打卡时间线可见与打卡图片清晰度两个个人开关`

---

### Task 3: 网页打卡上时间线（带私聊标记）

**Files:**
- Modify: `webapp/profile/checkin_service.py`（perform_checkin 增事件上传）
- Test: 新建 `test/test_web_checkin_emit.py`

**Interfaces:**
- Consumes: Task 1 的 `insert(..., is_private=)`；`core.timeline_client.emit_event`；`webapp.gallery.thumbnails.ensure_thumbnail`。
- Produces: 网页打卡事件 `source="checkin"`，`data={"images": ["/thumb/<uid>/<name>", ...], "private": True}`，`dedup_key="checkin:<uid>:<date>:web-<uuid>"`。

- [ ] **Step 1: 写失败测试** — `test/test_web_checkin_emit.py`：临时 DB + monkeypatch `webapp.profile.checkin_service.emit_event` 捕获 payload（同 Task 1 模式），调 `perform_checkin(user_id, ["webfake0.jpg"])`，断言：捕获 1 条、`data["private"] is True`、`data["images"][0] == "/thumb/<uid>/webfake0.jpg"`、`dedup_key` 前缀 `checkin:<uid>:`、checkin_records.is_private=1。图片落盘与缩略图生成用 stub（monkeypatch `_save_one_image` 路径或预置文件）。
- [ ] **Step 2: 跑 RED** — FAIL（无 emit 调用）。
- [ ] **Step 3: 实现** — `perform_checkin` 在 `db.checkin.insert(...)` 改为 `db.checkin.insert(user_id, image_names, message_id=None, is_private=True)`，并在结算完成、返回 summary 前追加（与 bot 侧事件结构对齐）：
```python
    from core.timeline_client import emit_event  # 模块顶部
    from webapp.gallery.thumbnails import ensure_thumbnail
    from webapp.gallery import config as gallery_config  # IMAGE_ROOT 对应的原图目录按实际 import

    for name in image_names:
        src = config.IMAGE_ROOT / str(user_id) / name
        if src.is_file():
            ensure_thumbnail(src)  # 首屏即可用 /thumb/ URL
    emit_event(
        source="checkin",
        actor_id=user_id,
        actor_qq=user_id,
        title="{id:%s} 完成打卡" % user_id,
        description="本周第 %d 次" % len(checkin_list),
        data={"images": ["/thumb/%s/%s" % (user_id, n) for n in image_names], "private": True},
        dedup_key="checkin:%s:%s:web-%s" % (user_id, datetime.now().strftime("%Y-%m-%d"), uuid.uuid4().hex[:8]),
    )
```
（import 路径与 `description` 措辞执行时以 bot 侧事件为准保持一致；`checkin_list` 为函数内既有周计数变量。）
- [ ] **Step 4: 跑 GREEN** — 新测试 + `python -m pytest test/test_webapp_api_suites.py -v`（webapp 套件回归）。
- [ ] **Step 5: Commit** — `feat(网页打卡): 网页打卡上传时间线并标记为私聊打卡`

---

### Task 4: 时间线读侧过滤与模糊图（服务端核心）

**Files:**
- Modify: `webapp/timeline/app.py`（feed/poll/new 三路径可见性过滤 + 序列化加 self_only 与模糊 URL）
- Modify: `webapp/gallery/thumbnails.py`（`ensure_blurred`）
- Modify: `webapp/gallery/app.py`（`/thumb/` 路由加 `?blur=1`）
- Test: 新建 `test/scripts/check_timeline_privacy.py`（子进程脚本，自动发现进回归）
- Docs 同 commit: `specs/web-gallery.md`

**Interfaces:**
- Consumes: Task 1/3 的 `data.private`；Task 2 的 `private_checkin_public` / `checkin_image_public`。
- Produces: 序列化事件新增可选字段 `self_only: true`（仅作者可见的被隐藏私聊打卡，前端据此渲染角标）；非作者查看模糊作者图片时 `data.images` URL 改写为 `/thumb/...?...blur=1`。
- 路由契约：`GET /thumb/{user_id}/{filename}?blur=1` 返回该缩略图的高斯模糊版（缓存于 THUMB_CACHE_DIR/blur-<digest>.jpg）。

- [ ] **Step 1: 写失败测试** — `test/scripts/check_timeline_privacy.py`（照 check_timeline_unread.py 子进程模式：独立临时 DB + 临时 SETTINGS_ROOT 环境变量）：
  种事件：A 的私聊打卡（data.private=true）、A 的群聊打卡（无 private）、B 的打卡（图 2 张）；种设置：A.private_checkin_public=false、A.checkin_image_public=false。断言（用 TestClient 或 HTTP 直连，照既有脚本）：
  1. 查看者 C 的 `/api/timeline`：看不到 A 的私聊打卡；看得到 A 的群聊打卡；A 的图片 URL 带 `blur=1`。
  2. 查看者 A 自己：看得到自己的私聊打卡且 `self_only == true`；自己图片无 `blur=1`。
  3. `/api/timeline/poll` 对 C 的新事件计数不含被隐藏事件；`/api/timeline/new` 同理。
  4. `GET /thumb/<...>?blur=1` 返回 200 且 Content-Type 图片（字节与原图不同）。
- [ ] **Step 2: 跑 RED** — `python test/scripts/check_timeline_privacy.py` FAIL。
- [ ] **Step 3: 实现**

`webapp/timeline/app.py` 顶部 import `from core import user_settings`，新增模块级：
```python
def _checkin_visibility(rows):
    """返回 (hidden_ids, blur_actor_ids, self_only_ids)。仅按作者 JSON 设置 × 事件 data.private 计算，历史无标记=公开。"""
    hidden, blur, self_only = set(), set(), set()
    actor_flags = {}  # actor_qq -> (private_public, image_public)，页内去重只读一次
    for row in rows:
        (_seq, eid, source, _rat, actor_id, actor_qq, *_rest, data_raw, _dk) = _row_named(row)
        if source != "checkin":
            continue
        key = str(actor_qq or actor_id)
        if key not in actor_flags:
            actor_flags[key] = (user_settings.private_checkin_public(key),
                                user_settings.checkin_image_public(key))
        private_public, image_public = actor_flags[key]
        if not image_public:
            blur.add(key)  # 该作者的全部打卡图对非作者模糊
        data = _loads(data_raw) or {}
        if data.get("private") and not private_public:
            hidden.add(eid)
            self_only.add(eid)  # 作者自见标记由调用方按 viewer 过滤
    return hidden, blur, self_only
```
（行解包以 `page()`/`page_unread_after()` 实际列序为准，抽小函数 `_row_named` 或直接索引；`blur_actor_ids` 为 `checkin_image_public=False` 的作者集合。）

三路径接入：
- `timeline_feed`：循环取页（上限 5 页）直到填满 limit 或无更多——每页 `db.timeline.page(cur, limit+1)` 后按 `hidden - {viewer 自见豁免}` 过滤（`hidden` 命中且 `viewer == 作者` → 保留并标 self_only，否则剔除），`next_cursor` 取**实际返回**的最后一行。
- `timeline_new`：`page_unread_after` 结果同样过滤后返回（数量可能少于 limit，`next_after` 仍取已消费最大 rowid，正确推进）。
- `timeline_poll`：新增 `db.timeline.rows_unread_after(user_id, lower)`（轻量列 rowid/id/source/actor/data；照 `count_unread_after` 改造，SQL 全参数化）→ Python 过滤后 `len()`。`core/db/timeline.py` 同 commit。
- `_serialize_rows`：签名加 `viewer_id: str, hidden_ctx`；事件 dict 上——`eid in self_only_ids and str(actor)==viewer_id` 时加 `"self_only": True`；图片改写——`source=="checkin" and viewer != 作者 and 作者 blur` 时 `[u + ("&" if "?" in u else "?") + "blur=1" for u in images]`。

`webapp/gallery/thumbnails.py` 追加：
```python
def ensure_blurred(thumb: Path) -> Path:
    """缩略图的高斯模糊版（独立缓存）。 ponytail: 模糊缩略图而非原图——展示尺寸即缩略图，防泄漏足够。"""
    blurred = thumb.parent / f"blur-{thumb.name}"
    if blurred.is_file() and blurred.stat().st_mtime >= thumb.stat().st_mtime:
        return blurred
    with Image.open(thumb) as im:
        _to_rgb(im).filter(ImageFilter.GaussianBlur(radius=12)).save(blurred, "JPEG", quality=config.THUMB_JPEG_QUALITY)
    return blurred
```
（`from PIL import Image, ImageFilter`；radius 12 为一眼不可辨的默认，写在 config 旁注释即可，不另立配置项。）

`webapp/gallery/app.py` `serve_thumb`：加 `blur: bool = Query(default=False)`，blur 时 `FileResponse(ensure_blurred(ensure_thumbnail(source)))`。
- [ ] **Step 4: 跑 GREEN + 回归** — `python test/scripts/check_timeline_privacy.py` PASS + `python -m pytest test/test_webapp_api_suites.py test/test_dom_render_suites.py -v`。
- [ ] **Step 5: Docs 同 commit** — `specs/web-gallery.md` 时间线节补：可见性过滤规则（data.private × 作者设置 × 查看者）、self_only 字段、blur=1 参数、poll/new 同口径。
- [ ] **Step 6: Commit** — `feat(时间线): 打卡事件按作者隐私设置动态隐藏与图片高斯模糊`

---

### Task 5: 前端角标「仅自己可见」

**Files:**
- Modify: `webapp/static/timeline.js`（renderEvent）
- Test: 修改 `test/test_timeline_render.js`

- [ ] **Step 1: 失败测试** — 夹具加一条 `self_only: true` 的打卡事件（feedPayload 或第 6 节新事件），断言其卡片存在 `tl-self-only` 角标元素且 `textContent === "仅自己可见"`；再断言普通事件无该角标。
- [ ] **Step 2: RED** — `node test/test_timeline_render.js` FAIL。
- [ ] **Step 3: 实现** — renderEvent 头部组装处：
```javascript
    if (ev.self_only) {
      const badge = document.createElement("span");
      badge.className = "tl-self-only";
      badge.textContent = "仅自己可见";
      head.appendChild(badge);  // 卡片角落；样式在 timeline 所在页 CSS 补一个角标类（小号、低饱和）
    }
```
（`textContent` 直写，禁 innerHTML；CSS 一条规则加到现有时间线样式文件。）
- [ ] **Step 4: GREEN + 回归** — node 测试 + `python -m pytest test/test_dom_render_suites.py`。
- [ ] **Step 5: Commit** — `feat(时间线): 被隐藏的私聊打卡对作者显示仅自己可见角标`

---

### Task 6: 版本收尾

- [ ] **Step 1** — `core/config.py` bump `1.24.5 → 1.25.0`；`CHANGELOG.md` 在 `[未发布]` 后插入 `[1.25.0]`：
```markdown
## [1.25.0] - <日期>

### 新增

- **打卡隐私设置**：个人设置页新增两个开关——「私聊打卡显示在时间线上」（关闭后他人不可见，作者仍可见并带「仅自己可见」角标）与「打卡图片对他人清晰可见」（关闭后他人在时间线看到高斯模糊图）；私聊/网页打卡在打卡表与时间线事件携带私聊标记，历史数据不受影响；网页端打卡自此也上传时间线
```
- [ ] **Step 2** — 全量 `python -m pytest` + `node test/test_timeline_render.js`（唯一允许失败：预先存在的 test_trpg_session cp936）。
- [ ] **Step 3: Commit** — `chore(版本): 1.25.0 打卡隐私与时间线可见性`

---

## 收尾核验

- [ ] 分支 6 个 commit；`BOTERO_VERSION == "1.25.0"` 与 CHANGELOG 一致。
- [ ] 文档四处齐：DATABASE×2、timeline-protocol、web-gallery。
- [ ] 场景手验清单（子进程脚本已覆盖）：C 看 A 隐藏私聊打卡=不可见；A 自看=可见+角标；A 图对 C=模糊、对 A=原图；poll/new 计数口径一致；blur 缩略图缓存命中。

## 明确不做

- 不新增设置数据库表（用户裁定沿用 JSON）；不动图库页可见性；不迁移 char_public；不打通"未开放私聊插件"的部署（生产已开放）；不回填历史事件/历史行标记。
