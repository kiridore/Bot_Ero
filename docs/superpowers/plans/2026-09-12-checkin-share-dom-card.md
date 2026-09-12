# 打卡分享卡 DOM 化 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 分享卡从前端 DOM 渲染预览（零网络），点「下载图片」时才 html-to-image 转 PNG；删除服务端 PIL 分享链路，新增同源头像代理。

**Architecture:** 预览 = 弹层内固定 1080px 逻辑宽 DOM 卡片（transform:scale 缩放）；数据全来自已加载的 `profileData` + lightbox 记录；头像经新路由 `GET /api/me/avatar.png`（磁盘缓存同源代理，QQ CDN 无 CORS 无法内联）。技术复刻活动分享长图（vendored `html-to-image.min.js`）。

**Tech Stack:** 原生 JS/CSS + html-to-image（已 vendored）；FastAPI 同步路由。

**Spec:** `docs/superpowers/specs/2026-09-12-checkin-share-dom-card-design.md`（取代 `2026-09-12-profile-checkin-tab-share-card-design.md` 的 D3/D4/D5，修订 D6/D7）

## Global Constraints

- **Commit 纪律**：每任务照常 commit（供审查出 diff），Task 3 最终 `git reset --soft <BASE>` squash 为**单个** commit `refactor(个人中心): 分享卡改DOM渲染下载时转图`（1.46.0 未发布，CHANGELOG 原地修订不 bump）。
- webapp 同步 `def` 路由；bot 进程禁 async；一律 `?` 参数化 SQL。
- 脚本套件经 `test/scripts/_env.py::write_config` 临时配置，绝不触真实 `server_data`；monkeypatch 模块属性做 file:// 伪头像源（先例：avatar_helper 测试钩子）。
- 分支 `feat/checkin-share-dom-card`，BASE = 起点 HEAD。
- html-to-image 不新增依赖（`webapp/static/vendor/html-to-image.min.js` 已存在，活动页在用）。
- 不动打卡列表 API/Tab/网格；本变更只影响分享链路与 profile 响应字段。

---

### Task 1: 后端——删 PIL 分享链路 + avatar 代理路由 + profile 字段

**Files:**
- Test: `test/scripts/check_profile_checkins.py`（改写分享相关用例）
- Create: `webapp/profile/avatar_service.py`
- Modify: `webapp/profile/app.py`（删 share 路由/import，加 avatar 路由）
- Modify: `webapp/profile/profile_service.py`（`build_profile` 加一字段）
- Delete: `webapp/profile/share_service.py`、`core/gen_image/checkin_share_card.py`、`test/test_checkin_share_card.py`
- Modify: `webapp/gallery/repository.py`（删 `fetch_checkin_by_id`）

**Interfaces:**
- Consumes: `resolve_avatar_url`（core.onebot_client）、`db.checkin.count_images`（已存在）
- Produces: `avatar_service.cached_avatar_path(user_id: str) -> Path | None`（模块属性 `resolve_avatar_url` 可被测试 monkeypatch）；路由 `GET /api/me/avatar.png`（200 PNG + `Cache-Control: private, max-age=86400` / 404「头像不可用」）；`/api/me/profile` 响应含 `total_checkin_images: int`。Task 2 前端依赖这三个。

- [ ] **Step 1: 改写脚本套件（RED）**

`test/scripts/check_profile_checkins.py` 中，从 `# --- 分享卡 ---` 注释起到 `rm = client.get(...)` 「无文件 404」check 止的整段替换为：

```python
# --- 头像同源代理（DOM 转图依赖；无 OneBot 源时降级 404） ---
r404a = client.get("/api/me/avatar.png", headers=MH)
check("avatar 无源 404", r404a.status_code == 404, str(r404a.status_code))

from webapp.profile import avatar_service  # noqa: E402

src_png = os.path.join(_tmp, "avatar_src.png")
with open(src_png, "wb") as f:
    f.write(_png(16, 16))
_orig_url = avatar_service.resolve_avatar_url
avatar_service.resolve_avatar_url = lambda uid: "file://" + src_png
try:
    ra = client.get("/api/me/avatar.png", headers=MH)
    check("avatar 200", ra.status_code == 200, str(ra.status_code))
    check("avatar png magic", ra.content[:8] == b"\x89PNG\r\n\x1a\n")
    check("avatar cache-control", "max-age=86400" in ra.headers.get("cache-control", ""))
finally:
    avatar_service.resolve_avatar_url = _orig_url
rb = client.get("/api/me/avatar.png", headers=MH)
check("avatar 二次命中缓存", rb.status_code == 200 and rb.content[:8] == b"\x89PNG\r\n\x1a\n")

# --- PIL 分享链路已删除 ---
rs = client.get(f"/api/me/checkin/{rid}/share.png", headers=MH)
check("旧分享路由已移除 404", rs.status_code == 404, str(rs.status_code))

# --- profile 字段 ---
rp = client.get("/api/me/profile", headers=MH)
dp = rp.json()
check("profile 200", rp.status_code == 200, str(rp.status_code))
check("total_checkin_images=26", dp.get("total_checkin_images") == 26, str(dp.get("total_checkin_images")))
```

（口径：25 条带文件 + 1 条 missing.png 记录 = 26 非补卡记录；`rid` 变量取自上方分页段已有的 `d1["items"][0]["id"]`。随后原有的「未登录 401」check 保持不动。）

- [ ] **Step 2: 跑套件确认失败**

Run: `python test/scripts/check_profile_checkins.py`
Expected: FAIL（`avatar 无源 404` 实为 404 能过，但 `avatar 200` 404、`total_checkin_images` None、模块导入等失败）

- [ ] **Step 3: 新建 avatar_service.py**

```python
"""分享卡头像：磁盘缓存 + 同源代理（DOM 转图需同源，QQ CDN 无 CORS 头）。"""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

from core import context
from core.onebot_client import resolve_avatar_url

logger = logging.getLogger(__name__)


def cached_avatar_path(user_id: str) -> Path | None:
    """命中/写满 avatar_cache/share_{uid}.png 并返回路径；任何失败返回 None。"""
    cache_path = Path(context.python_data_path) / "avatar_cache" / f"share_{user_id}.png"
    if cache_path.is_file():
        return cache_path
    url = resolve_avatar_url(user_id)
    if not url:
        return None
    try:
        if url.startswith("file://"):  # 测试钩子，同 avatar_helper 先例
            content = Path(url.removeprefix("file://")).read_bytes()
        else:
            r = requests.get(url, timeout=6)
            r.raise_for_status()
            content = r.content
        im = Image.open(BytesIO(content))
        im.load()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        im.convert("RGB").save(cache_path, format="PNG")
        return cache_path
    except Exception:
        logger.warning("分享卡头像获取失败 user=%s", user_id, exc_info=True)
        return None
```

- [ ] **Step 4: app.py 改路由**

- 删除 `from webapp.profile.share_service import build_share_png`
- `from fastapi.responses import FileResponse, Response` 改回 `from fastapi.responses import FileResponse`
- 新增 `from webapp.profile.avatar_service import cached_avatar_path`
- 删除整个 `api_checkin_share_png` 路由，替换为：

```python
@router.get("/api/me/avatar.png")
def api_my_avatar_png(
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    path = cached_avatar_path(user_id)
    if path is None:
        raise HTTPException(status_code=404, detail="头像不可用")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=86400"})
```

- [ ] **Step 5: profile_service.py 加字段**

`build_profile` 返回 dict 中 `"points": db.points.get(user_id),` 行后加：

```python
        "total_checkin_images": db.checkin.count_images(user_id),
```

- [ ] **Step 6: 删除死代码**

```bash
git rm webapp/profile/share_service.py core/gen_image/checkin_share_card.py test/test_checkin_share_card.py
```

`webapp/gallery/repository.py` 删除 `fetch_checkin_by_id` 整个函数（文件末尾）。

- [ ] **Step 7: 跑套件确认通过**

Run: `python test/scripts/check_profile_checkins.py`
Expected: 全部 ok，`PASS: 0 failures`

Run: `python -m pytest test/test_webapp_api_suites.py -q`
Expected: 全部 passed

- [ ] **Step 8: Commit**

```bash
git add -A -- webapp/profile/avatar_service.py webapp/profile/app.py webapp/profile/profile_service.py webapp/gallery/repository.py test/scripts/check_profile_checkins.py
git add -u webapp/profile/share_service.py core/gen_image/checkin_share_card.py test/test_checkin_share_card.py
git commit -m "refactor(个人中心): 后端删PIL分享链路并新增头像同源代理"
```

---

### Task 2: 前端——DOM 分享卡 + 下载时转图

**Files:**
- Modify: `webapp/static/profile.html`（引 html-to-image；弹层 body 改容器；下载改 button）
- Modify: `webapp/static/profile.js`（记录对象化、卡片构建、缩放预览、下载转换）
- Modify: `core/web/static/profile.css`（.share-card 系列样式；bump `?v=3`→`?v=4`）

**Interfaces:**
- Consumes: Task 1 的 `/api/me/avatar.png` 与 `profileData.total_checkin_images`；`/api/me/day` 与 `/api/me/checkins` 的 item（均含 id/image_url/checkin_date）
- Produces: DOM 契约 `#shareCardHost`（预览容器）、`#shareDownload`（button）、`.share-card` 系列类；`openLightbox(record)` 新签名（record={id,image_url,checkin_date}）

- [ ] **Step 1: profile.html**

- 头部脚本区，`profile.js` 引入行**之前**加：`<script src="/static/vendor/html-to-image.min.js"></script>`
- `<div class="share-dialog-body"><img id="shareImg" ... /></div>` 改为：`<div class="share-dialog-body"><div id="shareCardHost"></div></div>`
- `<a id="shareDownload" class="share-download" download="checkin-share.png">下载图片</a>` 改为：`<button type="button" id="shareDownload" class="share-download">下载图片</button>`
- `profile.css?v=3` → `?v=4`

- [ ] **Step 2: profile.css**

删除旧 `.share-dialog-body img {...}` 规则，追加（并保留其余 share-dialog 规则）：

```css
.share-card-host {
  overflow: hidden;
}

.share-card {
  width: 1080px;
  background: #f5f5f5;
  color: #2d2d2d;
  padding: 36px 40px 32px;
  box-sizing: border-box;
  transform-origin: top left;
}

.share-card-header {
  display: flex;
  align-items: center;
  gap: 20px;
}

.share-card-avatar {
  width: 96px;
  height: 96px;
  border-radius: 50%;
  object-fit: cover;
  flex: none;
}

.share-card-initial {
  width: 96px;
  height: 96px;
  border-radius: 50%;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e1e4e9;
  color: #2d2d2d;
  font-size: 44px;
}

.share-card-name {
  font-size: 40px;
  font-weight: 700;
}

.share-card-date {
  margin-top: 12px;
  font-size: 28px;
  color: #6e6e6e;
}

.share-photo {
  position: relative;
  margin-top: 24px;
  overflow: hidden;
}

.share-photo-bg {
  position: absolute;
  inset: -40px;
  background-position: center;
  background-size: cover;
  filter: blur(40px) brightness(1.08);
}

.share-photo img {
  position: relative;
  display: block;
  max-width: 1000px;
  max-height: 1250px;
  margin: 0 auto;
}

.share-card-stats {
  margin-top: 28px;
  font-size: 30px;
  color: #6e6e6e;
}

.share-card-footer {
  margin-top: 16px;
  font-size: 26px;
  color: #6e6e6e;
  text-align: right;
}
```

`.share-download` 规则追加按钮兼容（保留原 `<a>` 风格底色）：`border: none; cursor: pointer; font-family: inherit;`

- [ ] **Step 3: profile.js**

顶部元素引用区：删除 `shareImg` 相关；`let currentRecordId = null;` 改为 `let currentRecord = null;`。

`openLightbox` 换签名（两个调用点 `appendCheckinCards`/`openDay` 改传整个 item）：

```js
function openLightbox(record) {
  lightboxImg.src = record.image_url;
  currentRecord = record;
  const shareBtn = document.getElementById("lightboxShare");
  if (shareBtn) shareBtn.classList.toggle("hidden", record.id == null);
  lightbox.classList.remove("hidden");
}
```

旧的 `openShareCard` 及 `shareDownload` href 逻辑替换为：

```js
const WEEKDAY_CN = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

function formatCheckinDateCN(s) {
  const d = new Date(String(s).replace(" ", "T"));
  if (isNaN(d)) return s;
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${WEEKDAY_CN[d.getDay()]} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function buildShareCardNode(record) {
  const p = profileData || {};
  const name = p.display_name || "打卡用户";
  const card = document.createElement("div");
  card.className = "share-card";

  const header = document.createElement("div");
  header.className = "share-card-header";
  const avatar = document.createElement("img");
  avatar.className = "share-card-avatar";
  avatar.src = "/api/me/avatar.png";
  avatar.alt = name;
  const initial = document.createElement("div");
  initial.className = "share-card-initial";
  initial.textContent = name.trim().slice(0, 1) || "?";
  avatar.onerror = () => avatar.replaceWith(initial);
  const headText = document.createElement("div");
  const nameEl = document.createElement("div");
  nameEl.className = "share-card-name";
  nameEl.textContent = name;
  const dateEl = document.createElement("div");
  dateEl.className = "share-card-date";
  dateEl.textContent = formatCheckinDateCN(record.checkin_date);
  headText.append(nameEl, dateEl);
  header.append(avatar, headText);

  const photo = document.createElement("div");
  photo.className = "share-photo";
  const bg = document.createElement("div");
  bg.className = "share-photo-bg";
  bg.style.backgroundImage = `url("${record.image_url}")`;
  const img = document.createElement("img");
  img.src = record.image_url;
  img.alt = "打卡图片";
  photo.append(bg, img);

  const stats = document.createElement("div");
  stats.className = "share-card-stats";
  const streak = (p.streaks && p.streaks.current_daily) || 0;
  stats.textContent = `连续打卡 ${streak} 天 · 累计 ${p.total_checkin_images || 0} 张`;

  const footer = document.createElement("div");
  footer.className = "share-card-footer";
  footer.textContent = "Power by 小埃同学";

  card.append(header, photo, stats, footer);
  return card;
}

function openShareCard() {
  if (!currentRecord) return;
  shareDialog.showModal(); // 先开弹层，hidden 状态下 clientWidth 为 0
  const host = document.getElementById("shareCardHost");
  host.innerHTML = "";
  const node = buildShareCardNode(currentRecord);
  host.appendChild(node);
  const scale = host.clientWidth / 1080;
  node.style.transform = `scale(${scale})`;
  host.style.height = node.offsetHeight * scale + "px";
}

async function downloadShareCard() {
  const node = document.querySelector("#shareCardHost .share-card");
  if (!node || typeof htmlToImage === "undefined") return;
  const btn = document.getElementById("shareDownload");
  btn.disabled = true;
  btn.textContent = "生成中…";
  try {
    const dataUrl = await htmlToImage.toPng(node, {
      width: 1080,
      height: node.offsetHeight,
      pixelRatio: 1,
      backgroundColor: "#f5f5f5",
      style: { transform: "none" },
    });
    const a = document.createElement("a");
    a.href = dataUrl;
    a.download = `checkin-${currentRecord.id}.png`;
    a.click();
  } catch (err) {
    alert(`生成分享卡失败：${(err && err.message) || err}`);
  } finally {
    btn.disabled = false;
    btn.textContent = "下载图片";
  }
}
```

事件绑定区：`shareDownload` 由 href 赋值改为 `document.getElementById("shareDownload").addEventListener("click", downloadShareCard);`（`lightboxShareBtn` 绑定 openShareCard 不变）。

- [ ] **Step 4: 验证**

Run: `node --check webapp/static/profile.js`
Run: `python -m pytest test/test_webapp_api_suites.py -q`
Expected: 均通过

- [ ] **Step 5: Commit**

```bash
git add webapp/static/profile.html webapp/static/profile.js core/web/static/profile.css
git commit -m "refactor(个人中心): 分享卡DOM预览与下载时转图"
```

---

### Task 3: 文档 + squash 单 commit

**Files:**
- Modify: `CHANGELOG.md`（原地修订 `[1.46.0]` 节，不 bump）
- Modify: `specs/web-gallery.md`（share.png 行换 avatar.png 行）

- [ ] **Step 1: CHANGELOG `[1.46.0]`** 该条目整段替换为：

```markdown
- **个人中心打卡卡片 Tab 与分享卡**：个人主页「称号」区升级为「称号 / 打卡记录」并列 Tab，打卡记录按月分组、卡片式浏览全部打卡图（分页加载）；lightbox 查看打卡图新增「生成分享卡片」——前端 DOM 卡片即时预览（浅色卡：头像/昵称/日期星期/照片/连击与累计统计/品牌 footer），点「下载图片」才经 html-to-image 转换为 PNG；极端宽高比（全景、超长图）照片自动 contain 进 1000×1250 区域并以模糊背景铺满，成品恒定 1080 宽；头像走同源代理路由 `/api/me/avatar.png`（磁盘缓存 + max-age=86400，规避 QQ CDN 无 CORS 无法内联）
```

- [ ] **Step 2: specs/web-gallery.md** 删 `| GET | /api/me/checkin/{id}/share.png | ... |` 行，原位替换：

```markdown
| `GET` | `/api/me/avatar.png` | 必须 | 我的头像 PNG（同源代理 + 磁盘缓存，max-age=86400，无源 404） |
```

- [ ] **Step 3: 全量回归**

Run: `python -m pytest`
Expected: 全部 passed（基线 369 − 已删单测 6 = 363 左右，数量以实际为准、全绿即可）

- [ ] **Step 4: squash 单 commit**

```bash
git reset --soft <BASE>
git add CHANGELOG.md specs/web-gallery.md <Task1/2 全部文件>
git commit -m "refactor(个人中心): 分享卡改DOM渲染下载时转图"
```

（不得 `git add -A`；工作区 3 个既有 untracked 计划文件不入库。）
