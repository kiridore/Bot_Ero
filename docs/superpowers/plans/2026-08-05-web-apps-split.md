# 打卡图库功能拆分实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 checkin_gallery 单进程应用按功能域拆分为 6 个独立子应用（图库/个人中心/跑团/留言簿/闹钟/活动），共享 core 层，由导航主页聚合入口。

**Architecture:** 共享层上移（auth/onebot_client/TITLE_DEFS/config/auth.js → core/），DbManager 统一路径与 busy_timeout 并补 GuestbookManager/ActivityManager；每个功能域一个薄子应用目录（app.py + __main__.py + static/），独立端口，Caddy 反代子域名。渐进式：先基建 5 项，再试点留言簿，验收后按模板迁移其余 5 域，最后图库收尾改名。

**Tech Stack:** FastAPI + uvicorn + Python stdlib（sqlite3/json/importlib），前端 vanilla JS（不变）。

## Global Constraints

- 权威设计：`docs/superpowers/specs/2026-08-05-web-apps-split-design.md`（本计划与之一致，冲突以 spec 为准）
- 旧链接不做重定向，直接失效（Caddy 只配新子域）
- 所有子应用共享同一 `data.db`（WAL 已启用）+ 同一组 `BOTERO_*` 环境变量
- 登录：密钥即 token（HMAC），跨域通用；但 localStorage 按域名隔离，**每个子域首次访问需重新登录一次**（同一把密钥）
- 只搬文件、改 import，**不重写任何业务逻辑**（SQL 逐字迁移）；打卡逻辑合并重写明确范围外
- 每个域迁移含 4 件套：新子应用 + 图库瘦身 + 导航主页 entries.json 卡片 + 验证清单
- 提交消息：中文 Conventional Commits（`.githooks` 校验）
- 每任务验证清单含：新子应用 API/页面可用、`grep -r <域名> checkin_gallery/` 无残留、`python -m checkin_gallery` 冒烟正常、机器人 `python main.py` import 正常（`python -c "import plugins"` 代替，避免真连 WS）

---

### Task 1: 共享配置 core/config.py + DbManager 路径统一

**Files:**
- Create: `core/config.py`
- Modify: `core/database_manager.py:18-22`（连接路径与 busy_timeout）
- Modify: `checkin_gallery/config.py`（改为再导出 core.config，保持旧 import 兼容）

**Interfaces:**
- Consumes: 无（纯新建）
- Produces: `core.config` 模块：`PROJECT_ROOT`、`_path_from_env`、`DB_PATH`、`IMAGE_ROOT`、`TRPG_CHARS_ROOT`、`USER_SETTINGS_ROOT`、`ACTIVITY_ROOT`、`HOST`、`PORT`、`PAGE_SIZE_DEFAULT`、`PAGE_SIZE_MAX`、`REMEDY_MARKER`、`ONEBOT_HTTP_URL`、`ONEBOT_TOKEN`、`GROUP_ID`、`THUMB_CACHE_DIR`、`THUMB_MAX_WIDTH`、`THUMB_MAX_HEIGHT`、`THUMB_JPEG_QUALITY`、`AUTH_SALT`、`CHECKIN_MAX_IMAGES`、`CHECKIN_MAX_BYTES`——全部 env 读取逻辑从 `checkin_gallery/config.py` 原样搬入。后续所有子应用 `from core.config import ...`。

- [ ] **Step 1: 创建 `core/config.py`**

把 `checkin_gallery/config.py` 现有内容（`PROJECT_ROOT`、`_path_from_env`、全部常量、全部环境变量读取）逐字搬入，仅两处调整：
1. 模块 docstring 改为：`"""BotEro 共享配置：bot 与全部 Web 子应用共用的环境变量读取。"""`
2. `PROJECT_ROOT` 计算改为 `Path(__file__).resolve().parent.parent`（core 在项目根下一层，`parent.parent` 仍为项目根，与 checkin_gallery 原逻辑等价）

- [ ] **Step 2: `checkin_gallery/config.py` 改为再导出**

文件整体替换为：

```python
"""Web 配置（兼容层）：常量全部来自 core.config，保持旧 import 不破坏。"""

from core.config import *  # noqa: F401,F403
from core.config import (
    AUTH_SALT,
    CHECKIN_MAX_BYTES,
    CHECKIN_MAX_IMAGES,
    DB_PATH,
    GROUP_ID,
    HOST,
    IMAGE_ROOT,
    ONEBOT_HTTP_URL,
    ONEBOT_TOKEN,
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_MAX,
    PORT,
    PROJECT_ROOT,
    REMEDY_MARKER,
    THUMB_CACHE_DIR,
    THUMB_JPEG_QUALITY,
    THUMB_MAX_HEIGHT,
    THUMB_MAX_WIDTH,
    ACTIVITY_ROOT,
    TRPG_CHARS_ROOT,
    USER_SETTINGS_ROOT,
)
```

- [ ] **Step 3: DbManager 统一路径 + busy_timeout**

`core/database_manager.py` 的 `__init__` 改为：

```python
    def __init__(self):
        from core.config import DB_PATH

        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.cur = self.conn.cursor()
        init_schema(self.conn, self.cur)
```

（import 放函数内避免循环依赖——core.config 无依赖，放文件顶部亦可，二选一，函数内更稳。）

- [ ] **Step 4: 验证**

```bash
python3 -c "from core.config import DB_PATH; print(DB_PATH)"
python3 -c "from checkin_gallery import config; print(config.DB_PATH, config.PAGE_SIZE_DEFAULT)"
python3 -c "from core.database_manager import DbManager; db = DbManager(); print('busy_timeout:', db.conn.execute('PRAGMA busy_timeout').fetchone()[0]); db.conn.close()"
python3 -c "import plugins" 2>&1 | tail -1
```

Expected: 三行正常输出；busy_timeout 为 5000；`import plugins` 无 traceback（plugins 会用 DbManager，验证 bot 侧不破）。

- [ ] **Step 5: 冒烟：web 应用可启动**

```bash
python3 -m checkin_gallery --port 8890 >/dev/null 2>&1 &
sleep 2; curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8890/api/checkins; kill %1
```

Expected: 200（api 可访问即 app import 链正常）。

- [ ] **Step 6: 提交**

```bash
git add core/config.py core/database_manager.py checkin_gallery/config.py
git commit -m "refactor(网页): 配置收敛到 core.config 并统一 DbManager 数据库路径"
```

---

### Task 2: core/auth.py + core/onebot_client.py 上移

**Files:**
- Create: `core/auth.py`、`core/onebot_client.py`
- Modify: `plugins/gallery_login_key/__init__.py:4`、`checkin_gallery/app.py:14`、`checkin_gallery/profile_service.py`（import 行）
- Delete: `checkin_gallery/auth.py`、`checkin_gallery/onebot_client.py`

**Interfaces:**
- Consumes: Task 1 的 `core.config`（AUTH_SALT / ONEBOT_HTTP_URL / ONEBOT_TOKEN / GROUP_ID）
- Produces: `core.auth.make_login_key(user_id: int | str) -> str`、`core.auth.verify_login_key(key: str) -> str | None`；`core.onebot_client.resolve_display_name(user_id: str) -> str`、`core.onebot_client.resolve_avatar_url(user_id: str) -> str`（签名与行为不变）

- [ ] **Step 1: 创建 `core/auth.py`**

`checkin_gallery/auth.py` 全文件搬入，仅改第 5 行 import：`from checkin_gallery import config` → `from core.config import AUTH_SALT`，函数内 `config.AUTH_SALT` 改为 `AUTH_SALT`（共 2 处）。

- [ ] **Step 2: 创建 `core/onebot_client.py`**

`checkin_gallery/onebot_client.py` 全文件搬入，仅改 import：`from checkin_gallery import config` → `from core.config import GROUP_ID, ONEBOT_HTTP_URL, ONEBOT_TOKEN`，函数内 `config.` 前缀相应改为局部名（`config.GROUP_ID`→`GROUP_ID`、`config.ONEBOT_HTTP_URL`→`ONEBOT_HTTP_URL`、`config.ONEBOT_TOKEN`→`ONEBOT_TOKEN`，共 4 处）。

- [ ] **Step 3: 更新引用方**

1. `plugins/gallery_login_key/__init__.py:4`：`from checkin_gallery.auth import make_login_key` → `from core.auth import make_login_key`
2. `checkin_gallery/app.py:14`：`from checkin_gallery.onebot_client import ...` → `from core.onebot_client import ...`
3. `checkin_gallery/profile_service.py`：`from checkin_gallery.onebot_client import ...` → `from core.onebot_client import ...`
4. `checkin_gallery/app.py` 中 `from checkin_gallery.auth import verify_login_key`（约第 11 行）→ `from core.auth import verify_login_key`
5. 删除 `checkin_gallery/auth.py`、`checkin_gallery/onebot_client.py`

- [ ] **Step 4: 验证**

```bash
python3 -c "
from core.auth import make_login_key, verify_login_key
k = make_login_key(123456)
assert verify_login_key(k) == '123456', '密钥往返失败'
print('密钥往返 OK')
"
python3 -c "import plugins; print('plugins import OK')"
python3 -m checkin_gallery --port 8890 >/dev/null 2>&1 &
sleep 2; curl -s -o /dev/null -w "login: %{http_code}\n" -X POST http://127.0.0.1:8890/api/auth/login -H 'Content-Type: application/json' -d '{"key":"x"}'; kill %1
```

Expected: 密钥往返断言通过；`import plugins` 无 traceback；login 端点 401（说明路由与验证链路正常，密钥错返回 401 属预期）。

- [ ] **Step 5: 提交**

```bash
git add core/auth.py core/onebot_client.py checkin_gallery/app.py checkin_gallery/profile_service.py plugins/gallery_login_key/__init__.py
git rm checkin_gallery/auth.py checkin_gallery/onebot_client.py
git commit -m "refactor(网页): 认证与昵称客户端上移至 core 共享层"
```

---

### Task 3: core/title_defs.py + 四处 service 改造

**Files:**
- Create: `core/title_defs.py`
- Modify: `checkin_gallery/profile_service.py`（删 importlib 样板，改 import）、`checkin_gallery/checkin_service.py`（同）、`checkin_gallery/title_settings.py`（同）、`checkin_gallery/shop_service.py:10`（改 import）

**Interfaces:**
- Consumes: Task 1 的 `core.config.PROJECT_ROOT`
- Produces: `core.title_defs.TITLE_DEFS: dict`（模块级，从 `plugins/title/defs.py` 加载一次，key 为称号 id int）

- [ ] **Step 1: 创建 `core/title_defs.py`**

```python
"""称号定义：从 plugins/title/defs.py 加载一次，全 Web 子应用共享。"""

from pathlib import Path
import importlib.util

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFS_PATH = _PROJECT_ROOT / "plugins" / "title" / "defs.py"


def _load() -> dict:
    spec = importlib.util.spec_from_file_location("botero_title_defs", _DEFS_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "TITLE_DEFS", {})


TITLE_DEFS: dict = _load()
```

- [ ] **Step 2: 改造 4 个 service**

`checkin_gallery/profile_service.py`：
- 删除 `import importlib.util`、`from pathlib import Path` 行与 `_TITLE_MODULE_PATH`、`_load_title_defs()` 函数、`TITLE_DEFS = _load_title_defs()` 行（约第 8、16-28 行）
- 新增 `from core.title_defs import TITLE_DEFS`

`checkin_gallery/checkin_service.py`：
- 删除其 `_TITLE_MODULE_PATH`（指向 `plugins/title.py` 的 `evaluate_and_unlock_titles`，注意这个不是 defs）——**仅删除 importlib 样板，`evaluate_and_unlock_titles` 的加载方式保留**（它加载插件模块而非定义，见 Step 3 说明）

`checkin_gallery/title_settings.py`：
- 删除 `_TITLE_MODULE_PATH`（指向 `plugins/title.py` 的 `evaluate_and_unlock_titles`，保留加载逻辑）
- 删除 `from checkin_gallery.profile_service import TITLE_DEFS`（第 10 行），新增 `from core.title_defs import TITLE_DEFS`

`checkin_gallery/shop_service.py:10`：
- `from checkin_gallery.profile_service import TITLE_DEFS` → `from core.title_defs import TITLE_DEFS`

> 说明：`checkin_service.py` 与 `title_settings.py` 的 importlib 加载的是 `plugins/title.py` 的 `evaluate_and_unlock_titles` 函数（打卡结算/称号装备时调用 bot 侧逻辑），不是称号定义——这部分加载机制本次不动，只删 defs 相关样板。以各文件实际内容为准，凡加载 `defs.py` 的样板一律删除，加载 `title.py` 的保留。

- [ ] **Step 3: 验证**

```bash
python3 -c "
from core.title_defs import TITLE_DEFS
assert isinstance(TITLE_DEFS, dict) and len(TITLE_DEFS) > 0, 'TITLE_DEFS 为空'
print('TITLE_DEFS:', len(TITLE_DEFS), '条')
"
python3 -c "import checkin_gallery.app; print('app import OK')"
python3 -c "import plugins; print('plugins import OK')"
grep -rn "checkin_gallery.profile_service import TITLE_DEFS\|load_title_defs" checkin_gallery/ core/ || echo "无残留"
```

Expected: TITLE_DEFS 非空；两个 import OK；grep 无输出。

- [ ] **Step 4: 提交**

```bash
git add core/title_defs.py checkin_gallery/profile_service.py checkin_gallery/checkin_service.py checkin_gallery/title_settings.py checkin_gallery/shop_service.py
git commit -m "refactor(网页): 称号定义上移 core.title_defs 消除重复加载"
```

---

### Task 4: GuestbookManager + ActivityManager 补齐

**Files:**
- Create: `core/db/guestbook.py`
- Modify: `core/db/activity.py`（追加 4 个 web 查询方法）、`core/database_manager.py`（挂载 `self.guestbook`）
- Delete: `checkin_gallery/guestbook_service.py`（其逻辑被 GuestbookManager 取代，删除在本任务完成）

**Interfaces:**
- Consumes: 无
- Produces: `DbManager().guestbook.list_entries(viewer_user_id: str | None, page: int = 1, page_size: int = 30) -> dict`、`post_entry(user_id: str, content: str) -> dict`、`like_entry(user_id: str, entry_id: int) -> dict`（返回结构与原 guestbook_service 完全一致，含 `max_content_len`）；`DbManager().activity.list_activities() -> list[dict]`、`get_my_activities(user_id: str) -> list[dict]`、`get_activity(activity_id: int) -> dict | None`

- [ ] **Step 1: 创建 `core/db/guestbook.py`**

把 `checkin_gallery/guestbook_service.py` 的 3 个函数移植为 `GuestbookManager` 方法（SQL 逐字，逻辑不变）：

```python
from datetime import datetime

MAX_CONTENT_LEN = 500
PAGE_SIZE_DEFAULT = 30
PAGE_SIZE_MAX = 100


class GuestbookManager:
    def __init__(self, conn):
        self.conn = conn
        self.cur = conn.cursor()

    def list_entries(self, viewer_user_id=None, page=1, page_size=PAGE_SIZE_DEFAULT):
        # SQL 与返回结构与原 guestbook_service.list_entries 完全一致
        # （含 COUNT 子查询、排序、liked 判定、max_content_len 字段）
        ...  # 实现：将原函数体逐字搬入，删除函数内 `db = DbManager()` 行，改用 self.cur/self.conn

    def post_entry(self, user_id, content):
        ...  # 同上：值校验、INSERT、lastrowid

    def like_entry(self, user_id, entry_id):
        ...  # 同上：不存在/自赞/重复赞校验、INSERT、返回 like_count
```

**实现要求**：打开 `checkin_gallery/guestbook_service.py`，将 3 个函数体**逐字**搬到类方法中（保持 MAX_CONTENT_LEN=500、排序 `ORDER BY like_count DESC, e.created_at DESC, e.id DESC`、错误消息文案、时间格式 `%Y-%m-%d %H:%M:%S`），仅把 `db = DbManager()` 与 `db.cur`/`db.conn` 替换为 `self.cur`/`self.conn`，`db.conn.commit()` 保留为 `self.conn.commit()`。

- [ ] **Step 2: ActivityManager 追加 4 个方法**

打开 `core/db/activity.py`，在类末尾追加 3 个方法，SQL 从 `checkin_gallery/activity_service.py` **逐字**搬入（含子查询与 CASE 排序）：

```python
    # ── web 只读查询（原 activity_service 移植）──
    def list_activities(self):
        # 原 list_activities：act 循环里 status in (open, running) 时附 members
        # （members 查询的 user_id/nickname/seq/status，ORDER BY seq ASC）
        ...

    def get_my_activities(self, user_id):
        # 原 get_my_activities SQL 逐字搬入
        ...

    def get_activity(self, activity_id):
        # 原 get_activity：SELECT * + members（含 next_user_id/received_at/submitted_at/content/images）
        # images json.loads 处理保留；需要 import json
        ...
```

**实现要求**：原 `_rows` 辅助用 `sqlite3.Row` + `dict(r)`，`ActivityManager` 已有 `_row`/`_rows` 同款辅助（且已设 row_factory）。逐字搬 SQL 进 `_rows`/`_row` 调用即可；`list_activities` 的 members 子查询循环保留；`get_activity` 的 `json.loads` 需要时在文件顶部加 `import json`。

- [ ] **Step 3: DbManager 挂载 guestbook**

`core/database_manager.py`：
- import 加 `from core.db.guestbook import GuestbookManager`
- `__init__` 内加 `self.guestbook = GuestbookManager(self.conn)`

- [ ] **Step 4: 删除 guestbook_service.py**

`git rm checkin_gallery/guestbook_service.py`。此时 `checkin_gallery/app.py` 仍 import 它——**本任务暂时保留 app.py 引用不动**（Task 6 试点迁移时 app.py 才改用 DbManager.guestbook），因此 Step 5 验证不能 import checkin_gallery.app。这属于跨任务依赖：guestbook_service 的删除留到 Task 6，本任务只建 manager 与挂载。

- [ ] **Step 5: 验证**

```bash
python3 -c "
from core.database_manager import DbManager
db = DbManager()
r = db.guestbook.list_entries(None, 1, 5)
assert 'items' in r and 'total' in r, 'guestbook list 结构错误'
print('guestbook 只读查询 OK, total =', r['total'])
a = db.activity.list_activities()
assert isinstance(a, list), 'activity list 失败'
print('activity 只读查询 OK, count =', len(a))
db.conn.close()
"
python3 -c "import plugins; print('plugins import OK')"
```

Expected: 三个断言通过。注意：这是对真实 data.db 的只读查询，安全。

- [ ] **Step 6: 提交**

```bash
git add core/db/guestbook.py core/db/activity.py core/database_manager.py
git commit -m "feat(网页): 新增 GuestbookManager 并补齐 ActivityManager 只读查询"
```

---

### Task 5: 共享静态 /shared/auth.js

**Files:**
- Create: `core/web/static/auth.js`（git mv 自 `checkin_gallery/static/auth.js`）
- Modify: `checkin_gallery/app.py`（mount /shared）、`checkin_gallery/static/*.html`（11 个页面的 `<script src="/static/auth.js">` → `/shared/auth.js`）

**Interfaces:**
- Consumes: 无
- Produces: 所有子应用统一挂载 `/shared` → `core/web/static/`；页面脚本路径统一 `/shared/auth.js`

- [ ] **Step 1: 迁移文件**

```bash
mkdir -p core/web/static
git mv checkin_gallery/static/auth.js core/web/static/auth.js
```

- [ ] **Step 2: app.py 挂载**

`checkin_gallery/app.py` 末尾（`app.mount("/static", ...)` 之后）追加：

```python
from pathlib import Path as _Path
_SHARED_STATIC_DIR = _Path(__file__).resolve().parent.parent / "core" / "web" / "static"
app.mount("/shared", StaticFiles(directory=_SHARED_STATIC_DIR), name="shared")
```

（`Path`/`StaticFiles` 已导入，无需重复 import；若 `Path` 已在顶部 import，则直接复用。）

- [ ] **Step 3: 全部页面改引用**

```bash
grep -rln '/static/auth.js' checkin_gallery/static/ | xargs sed -i 's|/static/auth.js|/shared/auth.js|g'
grep -rn '/static/auth.js' checkin_gallery/static/ || echo "无残留"
```

- [ ] **Step 4: 验证**

```bash
python3 -m checkin_gallery --port 8890 >/dev/null 2>&1 &
sleep 2
curl -s -o /dev/null -w "shared auth.js: %{http_code}\n" http://127.0.0.1:8890/shared/auth.js
curl -s http://127.0.0.1:8890/ | grep -c "/shared/auth.js"
kill %1
```

Expected: auth.js 200；首页 HTML 中 `/shared/auth.js` 出现 1 次。

- [ ] **Step 5: 提交**

```bash
git add -A core/web/static checkin_gallery/app.py checkin_gallery/static
git commit -m "refactor(网页): 登录脚本移至共享静态目录 /shared/auth.js"
```

---

### Task 6: 试点——guestbook/ 子应用

**Files:**
- Create: `guestbook/__init__.py`、`guestbook/__main__.py`、`guestbook/app.py`、`guestbook/static/guestbook.html`（git mv）、`guestbook/static/guestbook.js`（git mv）
- Modify: `checkin_gallery/app.py`（删 guestbook 3 API + import + 页面路由）、`checkin_gallery/static/index.html`（删留言簿链接）、`checkin_gallery/static/profile.html`（删留言簿导航项）、`homepage/entries.json`（加卡片）
- Delete: `checkin_gallery/static/guestbook.html`、`checkin_gallery/static/guestbook.js`、`checkin_gallery/guestbook_service.py`（Task 4 留的引用在此清除）

**Interfaces:**
- Consumes: Task 1-5 全部（core.config、core.auth、core.onebot_client、core/web/static/auth.js、DbManager().guestbook）
- Produces: `guestbook` 包（`python -m guestbook` 起 8766 端口）；图库不再含留言簿

- [ ] **Step 1: 创建 `guestbook/app.py`**

```python
"""留言簿子应用：匿名展示，登录后可留言与点赞。"""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.auth import verify_login_key
from core.config import PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX
from core.database_manager import DbManager

STATIC_DIR = Path(__file__).resolve().parent / "static"
SHARED_STATIC_DIR = Path(__file__).resolve().parent.parent / "core" / "web" / "static"

app = FastAPI(title="BotEro 留言簿", version="1.0.0")


def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    uid = verify_login_key(authorization[7:].strip())
    if uid is None:
        raise HTTPException(status_code=401, detail="密钥无效")
    return uid


def get_optional_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return verify_login_key(authorization[7:].strip())


class GuestbookPostIn(BaseModel):
    content: str


def _or_400(fn, *args):
    try:
        return fn(*args)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/guestbook")
def api_guestbook_list(
    viewer_id: Annotated[str | None, Depends(get_optional_user_id)],
    page: int = Query(1, ge=1),
    page_size: int = Query(PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX),
):
    return DbManager().guestbook.list_entries(viewer_id, page, page_size)


@app.post("/api/guestbook")
def api_guestbook_post(
    body: GuestbookPostIn,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _or_400(DbManager().guestbook.post_entry, user_id, body.content)


@app.post("/api/guestbook/{entry_id}/like")
def api_guestbook_like(
    entry_id: int,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    return _or_400(DbManager().guestbook.like_entry, user_id, entry_id)


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "guestbook.html")


app.mount("/shared", StaticFiles(directory=SHARED_STATIC_DIR), name="shared")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
```

- [ ] **Step 2: 创建 `guestbook/__main__.py`**

```python
import argparse

import uvicorn

from core.config import HOST


def main():
    parser = argparse.ArgumentParser(description="BotEro 留言簿")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    print(f"访问: http://{args.host}:{args.port}/")
    uvicorn.run("guestbook.app:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
```

`guestbook/__init__.py` 创建为空文件。

- [ ] **Step 3: 迁移页面**

```bash
mkdir -p guestbook/static
git mv checkin_gallery/static/guestbook.html guestbook/static/guestbook.html
git mv checkin_gallery/static/guestbook.js guestbook/static/guestbook.js
```

修改 `guestbook/static/guestbook.html`：
1. `<script src="/static/auth.js">` → `/shared/auth.js`（`/static/guestbook.js` 不变）
2. 删除页内导航链接"← 图库"与"个人中心"（约第 12-16 行 `.back-link` 与 `guestbook-nav` 块，整块删除，仅保留页头标题）——群友从导航主页进入，子域间不互链
3. 其余内容与 `guestbook.js` **一字不改**

- [ ] **Step 4: 图库瘦身**

`checkin_gallery/app.py`：
1. 删除 import：`from checkin_gallery.guestbook_service import like_entry, list_entries, post_entry`（第 16 行）
2. 删除 3 个路由函数：`api_guestbook_list`（412-419）、`api_guestbook_post`（421-427）、`api_guestbook_like`（429-435）
3. 删除页面路由 `guestbook_page`（740-745）

`checkin_gallery/static/index.html`：删除工具栏"留言簿"链接（第 13 行 `<a href="/guestbook" class="toolbar-link">留言簿</a>`）

`checkin_gallery/static/profile.html`：删除导航栏 `<a href="/guestbook">留言簿</a>`（第 20 行附近）

`git rm checkin_gallery/guestbook_service.py`

- [ ] **Step 5: 导航主页加卡片**

`homepage/entries.json` 数组末尾追加：

```json
  {
    "name": "留言簿",
    "desc": "群友留言与点赞",
    "url": "https://guestbook.littlero.com"
  }
```

- [ ] **Step 6: 验证清单**

```bash
python3 -m guestbook --port 8891 >/dev/null 2>&1 &
python3 -m checkin_gallery --port 8890 >/dev/null 2>&1 &
sleep 2
curl -s -o /dev/null -w "guestbook 页面: %{http_code}\n" http://127.0.0.1:8891/
curl -s http://127.0.0.1:8891/ | grep -c "/shared/auth.js"
curl -s -o /dev/null -w "guestbook API: %{http_code}\n" http://127.0.0.1:8891/api/guestbook
curl -s http://127.0.0.1:8890/ | grep -c "guestbook" || echo "图库首页无 guestbook 引用"
curl -s http://127.0.0.1:8890/ | grep -c "/shared/auth.js"
grep -rn "guestbook" checkin_gallery/ || echo "checkin_gallery 无 guestbook 残留"
python3 -c "import plugins; print('plugins import OK')"
kill %1 %2 2>/dev/null
```

Expected: guestbook 页面/API 200；guestbook 页面含 1 处 `/shared/auth.js`；图库首页无 guestbook、含 1 处 `/shared/auth.js`；grep 无残留；plugins import OK。

- [ ] **Step 7: 提交**

```bash
git add guestbook homepage/entries.json
git rm checkin_gallery/guestbook_service.py
git add -u checkin_gallery/
git commit -m "feat(网页): 留言簿拆分为独立子应用（试点）"
```

---

### Task 7: 部署文档（Caddy + systemd）

**Files:**
- Create: `docs/web-apps-deployment.md`

**Interfaces:**
- Produces: VPS 部署参考文档，覆盖全部 6 子域

- [ ] **Step 1: 创建部署文档**

内容（完整写出）：
1. **DNS**：6 个子域 A 记录指向 VPS（gallery 保留现有记录）：`gallery.littlero.com`（已有）、`profile`、`trpg`、`guestbook`、`alarms`、`activities`（均为 `littlero.com` 子域，`@` 后缀示例照此模式）
2. **Caddyfile**：6 段 `reverse_proxy 127.0.0.1:<port>`（端口：gallery 8765 / guestbook 8766 / profile 8767 / trpg 8768 / alarms 8769 / activities 8770）。注明旧路径不重定向、直接失效
3. **systemd**：每个子应用一个 unit，示例给 `guestbook.service` 完整内容（WorkingDirectory=仓库路径、Environment 注入 `BOTERO_DB_PATH`/`BOTERO_AUTH_SALT`/`BOTERO_GALLERY_PORT=8766` 等、`ExecStart=/usr/bin/python3 -m guestbook`、Restart=always），其余 5 个按端口/模块名类推（列表注明：profile→`-m profile` 8767，trpg→`-m trpg` 8768，alarms→`-m alarms` 8769，activities→`-m activities` 8770，gallery→`-m checkin_gallery` 8765 保留原名直到 Task 12 改名）
4. **环境变量清单**：全部 `BOTERO_*` 变量名与用途（从 core/config.py 列出）
5. **导航主页**：`homepage/entries.json` 是唯一入口维护点

- [ ] **Step 2: 验证**

```bash
python3 -c "print(open('docs/web-apps-deployment.md').read().count('reverse_proxy'))"
```

Expected: 输出 `6`（6 个子域反代段齐全）。

- [ ] **Step 3: 提交**

```bash
git add docs/web-apps-deployment.md
git commit -m "docs(网页): 多子应用部署文档（Caddy+systemd+DNS）"
```

---

### Task 8: 迁移闹钟 → alarms/

**Files:**
- Create: `alarms/__init__.py`、`alarms/__main__.py`（port 8769）、`alarms/app.py`、`alarms/static/alarms.html`、`alarms/static/alarms.js`（git mv）
- Create: `alarms/alarm_service.py`（git mv `checkin_gallery/alarm_service.py`）
- Modify: `checkin_gallery/app.py`（删 3 API + import + 页面路由）、`checkin_gallery/static/profile.html`（删闹钟导航项）、`homepage/entries.json`
- Delete: `checkin_gallery/static/alarms.html`、`checkin_gallery/static/alarms.js`、`checkin_gallery/alarm_service.py`

**Interfaces:**
- Consumes: Task 1-5；`alarms/alarm_service.py` 与现文件内容完全一致（import 仅 `checkin_gallery.config` → `core.config` 变更，importlib 加载 plugins/group_alarm/parser.py 的模式保留）
- Produces: `alarms` 包（`python -m alarms` 8769）

- [ ] **Step 1: 迁移 service 与页面**

```bash
mkdir -p alarms/static
git mv checkin_gallery/alarm_service.py alarms/alarm_service.py
git mv checkin_gallery/static/alarms.html alarms/static/alarms.html
git mv checkin_gallery/static/alarms.js alarms/static/alarms.js
```

修改 `alarms/alarm_service.py`：`from checkin_gallery import config` → `from core.config import DB_PATH`（如用到其他常量逐一对应；仅改 import，逻辑一字不动）。

修改 `alarms/static/alarms.html`：`/static/auth.js` → `/shared/auth.js`；删除"← 图库"back 链接与个人中心导航项（按页面实际结构，保留标题即可）。

- [ ] **Step 2: 创建 `alarms/app.py`**

参照 Task 6 的 `guestbook/app.py` 骨架（FastAPI 实例、`get_current_user_id`/`get_optional_user_id`、`_or_400` 助手、`app.mount("/shared", ...)`、`app.mount("/static", ...)`），实现 3 个路由，逻辑调用 `alarms.alarm_service`（签名：`list_alarms(user_id)`、`create_alarm(user_id, payload: dict)`、`cancel_alarm(user_id, alarm_id)`，payload 结构与现 app.py 的 `AlarmCreateIn` 相同）：

1. `GET /api/me/alarms`（现 checkin_gallery/app.py:391-394，`api_alarms_list`）
2. `POST /api/me/alarms`（396-402，`api_alarms_create`，保留 `_checkin_or_400` 式 ValueError 处理）
3. `DELETE /api/me/alarms/{alarm_id}`（404-409，`api_alarms_cancel`）

`AlarmCreateIn` Pydantic 模型从 `checkin_gallery/app.py:99-113` 逐字搬入。

页面路由：`GET /` → `FileResponse(alarms/static/alarms.html)`。

`alarms/__main__.py` 参照 Task 6 Step 2（模块名 `alarms.app`，port 8769）。

- [ ] **Step 3: 图库瘦身**

`checkin_gallery/app.py`：删 import（`from checkin_gallery.alarm_service import ...` 第 16 行）、删 3 个闹钟路由（391-409）、删页面路由 `profile_alarms_page`（732-737）。`checkin_gallery/static/profile.html` 删"闹钟"导航项。

- [ ] **Step 4: 导航主页**

`homepage/entries.json` 追加：

```json
  {
    "name": "闹钟",
    "desc": "个人与群闹钟管理",
    "url": "https://alarms.littlero.com"
  }
```

- [ ] **Step 5: 验证**

```bash
python3 -m alarms --port 8892 >/dev/null 2>&1 &
python3 -m checkin_gallery --port 8890 >/dev/null 2>&1 &
sleep 2
curl -s -o /dev/null -w "alarms 页面: %{http_code}\n" http://127.0.0.1:8892/
curl -s -o /dev/null -w "alarms API: %{http_code}\n" http://127.0.0.1:8892/api/me/alarms
curl -s http://127.0.0.1:8892/ | grep -c "/shared/auth.js"
grep -rn "alarm" checkin_gallery/ || echo "checkin_gallery 无 alarm 残留"
python3 -c "import plugins; print('plugins import OK')"
kill %1 %2 2>/dev/null
```

Expected: 页面 200（API 未带 token 应 401，`-o /dev/null -w` 会显示 401——与图库现状一致，接受）；`/shared/auth.js` 1 处；grep 无残留；plugins OK。

- [ ] **Step 6: 提交**

```bash
git add alarms homepage/entries.json
git rm checkin_gallery/alarm_service.py checkin_gallery/static/alarms.html checkin_gallery/static/alarms.js
git add -u checkin_gallery/
git commit -m "feat(网页): 闹钟拆分为独立子应用"
```

---

### Task 9: 迁移跑团 → trpg/

**Files:**
- Create: `trpg/__init__.py`、`trpg/__main__.py`（port 8768）、`trpg/app.py`、`trpg/static/trpg.html`、`trpg/static/char_view.html`、`trpg/static/trpg.js`、`trpg/static/char_view.js`（git mv）
- Modify: `checkin_gallery/app.py`（删 7 API + 相关 import + 2 页面路由 + `CharOut`/`_char_to_out`）、`checkin_gallery/static/profile.html`（删跑团导航项）、`homepage/entries.json`
- Delete: `checkin_gallery/static/trpg.html`、`char_view.html`、`trpg.js`、`char_view.js`

**Interfaces:**
- Consumes: Task 1-5；core.character_store / core.trpg.character / core.trpg.rules / core.user_settings（保持 `from core...` import）
- Produces: `trpg` 包（`python -m trpg` 8768）

- [ ] **Step 1: 迁移页面**

```bash
mkdir -p trpg/static
git mv checkin_gallery/static/trpg.html trpg/static/trpg.html
git mv checkin_gallery/static/trpg.js trpg/static/trpg.js
git mv checkin_gallery/static/char_view.html trpg/static/char_view.html
git mv checkin_gallery/static/char_view.js trpg/static/char_view.js
```

两个 html 的 `/static/auth.js` → `/shared/auth.js`；删除"← 图库"/个人中心导航链接；其余不动。

- [ ] **Step 2: 创建 `trpg/app.py`**

从 `checkin_gallery/app.py` 迁移（逐字搬入，仅改 import 来源）：
- Pydantic 模型：`CharacterIn`（119-151）、`CharOut`（162-204）、`SettingsIn`/`SettingsOut`（154-159）
- 助手：`_char_to_out`（207-255，依赖 `trpg_char.finalize` 与 `resolve_display_name`）
- API 路由（共 7 个，逐字搬）：`api_my_characters`（471-479）、`api_create_character`（482-498）、`api_get_my_character`（500-508）、`api_update_character`（511-529）、`api_delete_character`（532-540）、`api_activate_character`（543-552）、`api_view_character`（555-571，含隐私校验 `user_settings_mod.privacy_public`）、`api_trpg_rules`（574-591）
- 页面路由 2 个：`GET /`（trpg.html）、`GET /char/{user_id}/{char_id}`（char_view.html，对应现 `/trpg/char/...`——**路径改为 `/char/...`**，char_view.js 里的链接也一并改）
- import：`from checkin_gallery.onebot_client import resolve_display_name` → `from core.onebot_client import resolve_display_name`；其余 `from core...` import 不变（character_store、user_settings_mod、trpg_char、trpg_rules）
- 认证助手 `get_current_user_id`（复制 Task 6 骨架版）
- `__main__.py`：模块名 `trpg.app`，port 8768
- mount `/shared` 与 `/static`

- [ ] **Step 3: 更新 char_view.js 的链接路径**

`trpg/static/char_view.js` 与 `trpg/static/trpg.js` 中所有 `/trpg/char/` 引用改为 `/char/`（`grep -rn '/trpg/char/' trpg/static/` 确认后替换）。

- [ ] **Step 4: 图库瘦身**

`checkin_gallery/app.py`：删相关 import（`from checkin_gallery.onebot_client` 若不再被其他路由使用则删除——注意 `/api/me/profile` 仍用 resolve_display_name，**profile_service 用自己的 import**，核对后删）、删 `CharacterIn`/`CharOut`/`SettingsIn`/`SettingsOut`/`_char_to_out` 模型与助手、删 8 个路由、删页面路由 `profile_trpg_page`（806-811）与 `trpg_char_view_page`（814-819）、删 import（`from core import character_store as char_store`、`from core import user_settings as user_settings_mod`、`from core.trpg import character as trpg_char`、`from core.trpg import rules as trpg_rules`——仅当 app.py 不再引用）。

`checkin_gallery/static/profile.html` 删"跑团"导航项。

- [ ] **Step 5: 导航主页**

```json
  {
    "name": "跑团",
    "desc": "DND 车卡与角色查看",
    "url": "https://trpg.littlero.com"
  }
```

- [ ] **Step 6: 验证**

```bash
python3 -m trpg --port 8893 >/dev/null 2>&1 &
python3 -m checkin_gallery --port 8890 >/dev/null 2>&1 &
sleep 2
curl -s -o /dev/null -w "trpg 页面: %{http_code}\n" http://127.0.0.1:8893/
curl -s -o /dev/null -w "trpg rules API: %{http_code}\n" http://127.0.0.1:8893/api/trpg/rules
curl -s http://127.0.0.1:8893/api/trpg/rules | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'attributes' in d; print('rules OK')"
grep -rn "trpg\|char_view\|character_store" checkin_gallery/ || echo "checkin_gallery 无 trpg 残留"
python3 -c "import plugins; print('plugins import OK')"
kill %1 %2 2>/dev/null
```

Expected: 页面 200；rules API 200 且含 attributes；grep 无残留；plugins OK。

- [ ] **Step 7: 提交**

```bash
git add trpg homepage/entries.json
git rm checkin_gallery/static/trpg.html checkin_gallery/static/trpg.js checkin_gallery/static/char_view.html checkin_gallery/static/char_view.js
git add -u checkin_gallery/
git commit -m "feat(网页): 跑团拆分为独立子应用"
```

---

### Task 10: 迁移活动 → activities/

**Files:**
- Create: `activities/__init__.py`、`activities/__main__.py`（port 8770）、`activities/app.py`、`activities/static/activities.html`、`activities/static/activities.js`、`activities/static/activities_detail.html`、`activities/static/activities_detail.js`（git mv）
- Modify: `core/db/activity.py`（Task 4 已加 list/get/my 查询——如活动列表还需 group_id 过滤等请对照，不需要则跳过）、`checkin_gallery/app.py`（删 4 API + import + 2 页面路由）、`checkin_gallery/static/profile.html`（删活动导航项）、`homepage/entries.json`
- Delete: `checkin_gallery/activity_service.py`、`checkin_gallery/static/activities*.html/js`

**Interfaces:**
- Consumes: Task 4 的 `DbManager().activity.list_activities/get_my_activities/get_activity`
- Produces: `activities` 包（`python -m activities` 8770）

- [ ] **Step 1: 迁移页面**

```bash
mkdir -p activities/static
git mv checkin_gallery/static/activities.html activities/static/activities.html
git mv checkin_gallery/static/activities.js activities/static/activities.js
git mv checkin_gallery/static/activities_detail.html activities/static/activities_detail.html
git mv checkin_gallery/static/activities_detail.js activities/static/activities_detail.js
```

两个 html 的 `/static/auth.js` → `/shared/auth.js`；删除 back 链接与导航项；页面间内部链接（activities.js → activities_detail.html）保持不变。

- [ ] **Step 2: 创建 `activities/app.py`**

骨架同 Task 6（FastAPI 实例、认证助手、`_or_400`、mount /shared 与 /static），数据访问全部走 `DbManager().activity`（不再自开连接），路由：

1. `GET /api/activities` → `{"items": db.activity.list_activities()}`（对照现 app.py:748-750）
2. `GET /api/me/activities` → `{"items": db.activity.get_my_activities(user_id)}`（753-755）
3. `GET /api/activities/{activity_id}`（758-767）：`get_activity` 判 None → 404；`members` 的 `images` 字段映射 `f"/archive/{activity_id}/media/{name}"`（逐字保留）
4. `GET /archive/{activity_id}/media/{filename}`（777-785）：路径守卫 `_assert_under_activity_root` 与 `_resolve_and_guard` 逻辑从现 app.py 逐字搬入（依赖 `core.config.ACTIVITY_ROOT`）
5. 页面路由：`GET /` → activities.html；`GET /{activity_id}` → activities_detail.html（对照现 `/archive/{id}`，**路径改为 `/{activity_id}`**，activities.js 里跳转链接同步改）
6. `GET /archive` → activities.html（可选保留，导航主页用 `https://activities.littlero.com/`，无需要可不加）

`activities/__main__.py`：模块名 `activities.app`，port 8770。

`activities/static/activities.js`：`/archive/` 开头的跳转改为新路径（`/api/activities` 保持；detail 跳转改为 `/{id}` 或按第 5 条实际路径）。

- [ ] **Step 3: 图库瘦身**

`checkin_gallery/app.py`：删 import（`from checkin_gallery.activity_service import ...` 第 10 行）、删 4 个活动路由（748-767）、删 `_assert_under_activity_root` 与 `serve_activity_media`（770-785）、删页面路由 `archive_page`（788-793）与 `activity_detail_page`（796-803）。

`checkin_gallery/static/profile.html` 删"活动"导航项。

- [ ] **Step 4: 导航主页**

```json
  {
    "name": "活动",
    "desc": "接龙与匹配活动的作品归档",
    "url": "https://activities.littlero.com"
  }
```

- [ ] **Step 5: 验证**

```bash
python3 -m activities --port 8894 >/dev/null 2>&1 &
python3 -m checkin_gallery --port 8890 >/dev/null 2>&1 &
sleep 2
curl -s -o /dev/null -w "activities 页面: %{http_code}\n" http://127.0.0.1:8894/
curl -s http://127.0.0.1:8894/api/activities | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'items' in d; print('activities API OK, count =', len(d['items']))"
grep -rn "activity" checkin_gallery/ || echo "checkin_gallery 无 activity 残留"
python3 -c "import plugins; print('plugins import OK')"
kill %1 %2 2>/dev/null
```

Expected: 页面 200；API 结构正确；grep 无残留；plugins OK。

- [ ] **Step 6: 提交**

```bash
git add activities homepage/entries.json
git rm checkin_gallery/activity_service.py checkin_gallery/static/activities.html checkin_gallery/static/activities.js checkin_gallery/static/activities_detail.html checkin_gallery/static/activities_detail.js
git add -u checkin_gallery/
git commit -m "feat(网页): 活动拆分为独立子应用"
```

---

### Task 11: 迁移个人中心 → profile/

**Files:**
- Create: `profile/__init__.py`、`profile/__main__.py`（port 8767）、`profile/app.py`、`profile/profile_service.py`、`profile/checkin_service.py`、`profile/shop_service.py`、`profile/title_settings.py`（git mv）、`profile/static/profile.html`、`profile/static/checkin.html`、`profile/static/shop.html`、`profile/static/settings.html`、`profile/static/profile.js`、`profile/static/checkin.js`、`profile/static/shop.js`、`profile/static/settings.js`、`profile/static/profile.css`、`profile/static/gallery.css`（按需，git mv）
- Modify: `checkin_gallery/app.py`（删个人域全部路由/模型/import）、`checkin_gallery/static/index.html`、`homepage/entries.json`
- Delete: `checkin_gallery/profile_service.py`、`checkin_gallery/checkin_service.py`、`checkin_gallery/shop_service.py`、`checkin_gallery/title_settings.py`、`checkin_gallery/static/profile*.html/js/css`、`checkin_gallery/static/checkin*`、`shop*`、`settings*`

**Interfaces:**
- Consumes: Task 1-5；core.title_defs（Task 3）；DbManager（含 guestbook/activity 等已挂载）
- Produces: `profile` 包（`python -m profile` 8767），聚合个人主页/打卡/商店/称号/设置 5 域

- [ ] **Step 1: 迁移 service 文件**

```bash
mkdir -p profile/static
git mv checkin_gallery/profile_service.py profile/profile_service.py
git mv checkin_gallery/checkin_service.py profile/checkin_service.py
git mv checkin_gallery/shop_service.py profile/shop_service.py
git mv checkin_gallery/title_settings.py profile/title_settings.py
```

批量改 import：`checkin_gallery.config` → `core.config`；`checkin_gallery.profile_service` → `profile.profile_service`；`checkin_gallery.onebot_client` → `core.onebot_client`（在 4 个文件内 `grep -rn "checkin_gallery" profile/*.py` 逐一替换，保留 `from core...` 与 importlib 加载 plugins 的路径逻辑不动——`_TITLE_MODULE_PATH` 等已由 Task 3 清理）。

- [ ] **Step 2: 迁移页面与样式**

```bash
git mv checkin_gallery/static/profile.html profile/static/profile.html
git mv checkin_gallery/static/profile.js profile/static/profile.js
git mv checkin_gallery/static/profile.css profile/static/profile.css
git mv checkin_gallery/static/checkin.html profile/static/checkin.html
git mv checkin_gallery/static/checkin.js profile/static/checkin.js
git mv checkin_gallery/static/shop.html profile/static/shop.html
git mv checkin_gallery/static/shop.js profile/static/shop.js
git mv checkin_gallery/static/settings.html profile/static/settings.html
git mv checkin_gallery/static/settings.js profile/static/settings.js
git mv checkin_gallery/static/gallery.css profile/static/gallery.css
```

修改各 html：`/static/auth.js` → `/shared/auth.js`；删除页内"← 图库"链接与已迁移域（留言簿/闹钟/跑团/活动）的导航项——**导航项只保留个人域内部**（个人主页/打卡/商店/设置/称号），引用本应用内路径；其余不动。gallery.css 若仅个人域页面使用则一并迁移，若图库首页还在用则复制一份保留在 checkin_gallery/static/（`grep -rn "gallery.css" checkin_gallery/static/*.html` 判断）。

- [ ] **Step 3: 创建 `profile/app.py`**

从 `checkin_gallery/app.py` 逐字迁移（改 import 来源为 `profile.*` 与 `core.*`）：
- Pydantic 模型：`SettingsIn`/`SettingsOut`（154-159，若 trpg 迁移后已删则重新从 git 历史取——**直接按 Task 9 之前原样写回**，内容同 spec 附录 A）、`EquippedTitlesIn`（87-89）、`EquipOneIn`（91-93）、`ShopRedeemIn`（95-97）、`AlarmCreateIn` 不需要（闹钟已迁走）
- 认证助手：`get_current_user_id`（282-290，复刻 Task 6 骨架版）
- 路由（逐字搬）：
  - 个人主页：`api_my_profile`（325-331）、`api_my_day`（333-343）
  - 称号：`_title_settings_or_400`（346-351）、`api_title_settings`（437-440）、`api_set_equipped`（442-447）、`api_equip_one`（450-455）、`api_clear_equipped`（458-461）、`api_unequip_one`（463-468）
  - 打卡：`_checkin_or_400`（353-357）、`api_checkin_status`（360-363）、`api_checkin_submit`（365-375，含 UploadFile 处理）
  - 商店：`api_shop`（378-380）、`api_shop_redeem`（383-388）
  - 设置：`api_my_settings`（594-597）、`api_update_settings`（600-607）
- 页面路由：`GET /` → profile.html；`GET /checkin`；`GET /shop`；`GET /settings`（对应现 `/profile/checkin` 等，**路径去掉 `/profile` 前缀**，页面间导航同步改）
- mount `/shared` 与 `/static`；`__main__.py` 模块名 `profile.app`，port 8767

- [ ] **Step 4: 页面导航路径调整**

`profile/static/*.html` 中所有 `/profile/xxx` 开头的链接改为 `/xxx`（如 `/profile/checkin` → `/checkin`）：`grep -rn "/profile" profile/static/` 逐一替换；JS 中同理（`grep -rn "/profile" profile/static/*.js`）。

- [ ] **Step 5: 图库瘦身**

`checkin_gallery/app.py` 删除全部已迁移内容后应只剩：认证 2 路由、图库 4 路由（checkins/users/thumb/media）、`/` 首页路由、静态 mount。删除：相关 import（`profile_service`、`checkin_service`、`shop_service`、`title_settings`、`repository` 保留——图库仍用 fetch_checkins_paginated 等）、全部 Pydantic 模型（除 `CheckinItemOut`/`CheckinListOut`/`UserOptionOut`/`UserIdsOut`/`LoginIn`/`SessionOut`/`DayCheckinsOut`）、`_checkin_to_out` 等图库专属助手保留。完成后的 app.py 应 <200 行。

`checkin_gallery/static/index.html`：删除"个人中心"相关链接（如有）与 `profile.js` 引用（如首页用）；**首页登录 dialog 保留**（登录后跳导航主页或不做跳转）。

- [ ] **Step 6: 导航主页**

```json
  {
    "name": "个人中心",
    "desc": "个人主页、打卡、商店与称号设置",
    "url": "https://profile.littlero.com",
    "span": 2
  }
```

- [ ] **Step 7: 验证**

```bash
python3 -m profile --port 8895 >/dev/null 2>&1 &
python3 -m checkin_gallery --port 8890 >/dev/null 2>&1 &
sleep 2
curl -s -o /dev/null -w "profile 页面: %{http_code}\n" http://127.0.0.1:8895/
curl -s -o /dev/null -w "profile day API: %{http_code}\n" "http://127.0.0.1:8895/api/me/day?date=2026-01-01"
curl -s -o /dev/null -w "gallery 首页: %{http_code}\n" http://127.0.0.1:8890/
curl -s -o /dev/null -w "gallery checkins: %{http_code}\n" http://127.0.0.1:8890/api/checkins
grep -rn "profile_service\|checkin_service\|shop_service\|title_settings" checkin_gallery/ || echo "checkin_gallery 无个人域 service 残留"
python3 -c "import plugins; print('plugins import OK')"
kill %1 %2 2>/dev/null
```

Expected: profile 页面 200、day API 401（未带 token，路由存在即可）；gallery 首页与 checkins 200；grep 无残留；plugins OK。

- [ ] **Step 8: 提交**

```bash
git add profile homepage/entries.json
git rm checkin_gallery/profile_service.py checkin_gallery/checkin_service.py checkin_gallery/shop_service.py checkin_gallery/title_settings.py checkin_gallery/static/profile.html checkin_gallery/static/profile.js checkin_gallery/static/profile.css checkin_gallery/static/checkin.html checkin_gallery/static/checkin.js checkin_gallery/static/shop.html checkin_gallery/static/shop.js checkin_gallery/static/settings.html checkin_gallery/static/settings.js
git add -u checkin_gallery/
git commit -m "feat(网页): 个人中心拆分为独立子应用（聚合主页/打卡/商店/称号/设置）"
```

---

### Task 12: 图库收尾——checkin_gallery → gallery/ 改名

**Files:**
- Create: `gallery/`（git mv 自 `checkin_gallery/` 剩余文件）
- Modify: `gallery/__main__.py`（uvicorn 模块名）、`gallery/app.py`（包内 import 改名）、`docs/web-apps-deployment.md`（Task 7 的 gallery 行更新）
- Delete: `checkin_gallery/`

**Interfaces:**
- Consumes: Task 11 完成后的精简 checkin_gallery（只剩图库）
- Produces: `gallery` 包（`python -m gallery` 8765）；仓库无 `checkin_gallery` 目录

- [ ] **Step 1: 检查残留**

```bash
ls checkin_gallery/ checkin_gallery/static/
```

Expected: 只剩 `__init__.py`、`__main__.py`、`app.py`、`config.py`（兼容层，见下）、`repository.py`、`thumbnails.py`、`dates.py`、`static/index.html`、`static/gallery.js`、`static/gallery.css`、`static/auth.js`（若 Task 5 后仍存在则一并 git mv）。**若还有未迁移文件，停下检查对应域任务是否漏了。**

- [ ] **Step 2: 改名**

```bash
git mv checkin_gallery gallery
```

- [ ] **Step 3: 包内 import 改名**

```bash
grep -rln "checkin_gallery" gallery/ | xargs sed -i 's/checkin_gallery/gallery/g'
grep -rn "checkin_gallery" gallery/ || echo "gallery 内无 checkin_gallery 引用"
```

`gallery/config.py` 兼容层保留（`from core.config import *` 再导出，供 gallery 内 repository/thumbnails/dates 的旧 import 继续工作——检查 `gallery/app.py` 的 `from gallery.config import ...` 已由 sed 统一改名）。

`gallery/__main__.py`：`uvicorn.run("gallery.app:app", ...)`（sed 已改，核对）。

- [ ] **Step 4: 全局残留检查**

```bash
grep -rn "checkin_gallery" --include="*.py" --include="*.md" --include="*.html" . | grep -v ".git/" || echo "全仓库无 checkin_gallery 残留"
```

若有残留（如文档、systemd 示例），逐一改为 `gallery`/`-m gallery`。

- [ ] **Step 5: 更新部署文档**

`docs/web-apps-deployment.md` 中 gallery 的 unit 示例：`ExecStart=/usr/bin/python3 -m checkin_gallery` → `-m gallery`。

- [ ] **Step 6: 验证**

```bash
python3 -m gallery --port 8890 >/dev/null 2>&1 &
sleep 2
curl -s -o /dev/null -w "gallery 首页: %{http_code}\n" http://127.0.0.1:8890/
curl -s -o /dev/null -w "gallery checkins: %{http_code}\n" http://127.0.0.1:8890/api/checkins
curl -s -o /dev/null -w "shared auth.js: %{http_code}\n" http://127.0.0.1:8890/shared/auth.js
python3 -c "import plugins; print('plugins import OK')"
kill %1 2>/dev/null
```

Expected: 三个 200；plugins OK。

- [ ] **Step 7: 导航主页图库卡片确认**

`homepage/entries.json` 打卡图库卡片 `url` 应为 `https://gallery.littlero.com`（如为占位域名则更新）。

- [ ] **Step 8: 提交**

```bash
git add -A gallery homepage/entries.json docs/web-apps-deployment.md
git rm -r checkin_gallery
git commit -m "refactor(网页): 图库更名 gallery 完成全部分拆"
```

---

## Self-Review 记录

**1. Spec 覆盖：**
- 拓扑/端口/域名 ✓（Task 6-12，gallery 8765 保留现域名、guestbook 8766、profile 8767、trpg 8768、alarms 8769、activities 8770）
- core/auth、core/onebot_client ✓（Task 2）
- DbManager 统一路径 + busy_timeout ✓（Task 1）；GuestbookManager/ActivityManager ✓（Task 4，ActivityManager 复用已存在的 core/db/activity.py）
- core/title_defs ✓（Task 3）
- 共享 auth.js ✓（Task 5）
- 试点留言簿 + 验证清单 ✓（Task 6）
- 模板化迁移其余 5 域 ✓（Task 8-12，每域含 4 件套）
- Caddy/systemd 部署文档 ✓（Task 7）
- 不兼容旧链接 ✓（各页面删除 back 链接，部署文档注明不重定向）
- 范围外（逻辑不重写、打卡不合并、旧链接不兼容）✓ 在 Global Constraints 与各任务"逐字搬入"约束中落实

**2. Placeholder 扫描：** 全部代码步骤给出实际内容或精确的来源文件+行号+迁移规则；无 TBD/TODO。Task 4 的 `...` 注释明确指向"打开原文件逐字搬入"并列出必须保持的细节（排序/文案/时间格式），来源存在，非占位。Task 11 的 SettingsIn/SettingsOut 引用"spec 附录 A"——原模型在 checkin_gallery/app.py:154-159，已注明从原文件写回。

**3. 命名/类型一致性：** `DbManager().guestbook.list_entries(viewer_user_id, page, page_size)` 在 Task 4 定义、Task 6 使用，签名一致；`core.auth.make_login_key/verify_login_key` Task 2 定义、Task 6+ 使用；`-m <module>` 与端口在各 `__main__.py` 与部署文档一致；`/shared/auth.js` 全计划统一。
