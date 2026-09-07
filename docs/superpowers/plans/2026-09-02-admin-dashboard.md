# 管理仪表盘 /admin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 网页端管理仪表盘：按群/私聊查看并修改插件启停（即时生效）+ config.yaml 在线编辑（校验/备份/原子写）；顺手修插件禁用重启复活与硬编码 data.db 两坑。

**Architecture:** 新 `webapp/admin/` 模块（5 端点，超管 403 守卫）复用 `group_plugin_config` 白名单表与 `core.context.SYSTEM_PLUGINS`；插件清单文件系统枚举（webapp 不 import plugins）；前端新静态三件套照 profile 系样式；bot 侧仅两处连接串与 migrate 播种语义修正。

**Tech Stack:** FastAPI 同步路由 + sqlite3 直连（照 context.py 既有模式）+ 原生 JS；测试 = 新 check 脚本 + 新 node DOM + 新进程内迁移测试。

**Spec:** `docs/superpowers/specs/2026-09-02-admin-dashboard-design.md`（D1–D7 与现状事实为准）

## Global Constraints

- bot 进程禁 async/await（webapp 路由同步 def）
- SQL 一律 `?` 参数化；webapp 不 import plugins（清单走 `config.PROJECT_ROOT/plugins` 文件系统枚举）
- admin 全部端点仅 `SUPER_USER`（`int(uid) in core.config.SUPER_USER`），非超管 403
- 配置写盘三步序：校验（safe_load + `_REQUIRED` 逐键非 None/""/[]）→ 备份 `.bak`（一代）→ tmp+`os.replace` 原子写；校验失败**绝不落盘**
- Commit 中文 + Conventional Commits，4 个逻辑 commit；Task 4 含 CHANGELOG `[1.36.0]` + `BOTERO_VERSION = "1.36.0"`
- 测试脚本用 `test/scripts/_env.py::write_config` 生成临时配置（`BOTERO_CONFIG`），路径常量属性访问
- 全量 `pytest` 全绿（基线 333 passed）

---

### Task 1: bot 侧两坑修复（migrate 播种语义 + DB_PATH）

**Files:**
- Modify: `core/context.py`（`is_plugin_enabled`、`migrate_group_plugin_config`）
- Modify: `plugins/group_manager/__init__.py`（3 处 `sqlite3.connect`）
- Create: `test/test_plugin_migrate.py`

**Interfaces:**
- Consumes: `config.DB_PATH`（`from core import config` 后属性访问）
- Produces: `migrate_group_plugin_config()` 仅在 `group_plugin_config` 表**不存在**时建表并播种默认群全量非系统插件；表已存在则直接返回

- [ ] **Step 1: 写失败测试**

创建 `test/test_plugin_migrate.py`：

```python
"""group_plugin_config 迁移播种语义：仅建表时播种，已有表禁用状态不得复活。

运行: python -m pytest test/test_plugin_migrate.py
"""

from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import config
import core.context as ctx


class MigrateSeedTest(unittest.TestCase):
    def setUp(self):
        # 指向 conftest 会话临时库（config.DB_PATH 已被 BOTERO_CONFIG 重定向）
        self.db = str(config.DB_PATH)
        conn = sqlite3.connect(self.db)
        conn.execute("DROP TABLE IF EXISTS group_plugin_config")
        conn.commit()
        conn.close()

    def _rows(self, gid):
        conn = sqlite3.connect(self.db)
        rows = conn.execute(
            "SELECT plugin_name FROM group_plugin_config WHERE group_id = ?", (gid,)
        ).fetchall()
        conn.close()
        return {r[0] for r in rows}

    def test_seed_only_when_table_created(self):
        # 注册表为空时（测试进程未注册插件），播种行数为 0 但表应被创建
        ctx.migrate_group_plugin_config()
        conn = sqlite3.connect(self.db)
        has = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'group_plugin_config'"
        ).fetchone() is not None
        conn.close()
        self.assertTrue(has, "表应被创建")

    def test_existing_table_not_reseeded(self):
        ctx.migrate_group_plugin_config()
        gid = config.DEFAULT_GROUP_ID
        # 手工模拟一个"禁用后"的状态：删掉一行 + 加一个自定义行
        conn = sqlite3.connect(self.db)
        conn.execute(
            "INSERT OR IGNORE INTO group_plugin_config (group_id, plugin_name) VALUES (?, ?)",
            (gid, "fake_plugin"),
        )
        conn.execute(
            "DELETE FROM group_plugin_config WHERE group_id = ? AND plugin_name = ?",
            (gid, "fake_plugin"),
        )
        conn.commit()
        conn.close()
        before = self._rows(gid)
        ctx.migrate_group_plugin_config()  # 再跑一次
        after = self._rows(gid)
        self.assertEqual(before, after, "表已存在时不得重新播种")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest test/test_plugin_migrate.py -v`
Expected: `test_existing_table_not_reseeded` FAIL（现行 migrate 无条件播种——注意：测试进程 plugin_registry 为空，播种行恒 0，此断言**恰不红**。实现 Step 1 时若发现该用例无法变红，改为直接断言「表已存在时不再执行任何 INSERT」：临时向 registry 注入假类后再跑 migrate，断言其行未出现——具体：`ctx.plugin_registry.append(FakeCls)`，FakeCls 的 `__module__ = "plugins.fake_plugin"`，migrate 后断言 `fake_plugin` 不在 rows 中。以注入版为准，删除弱断言版）

- [ ] **Step 3: 实现**

`core/context.py`：文件头部加 `from core import config`；`is_plugin_enabled` 内 `sqlite3.connect("data.db")` → `sqlite3.connect(str(config.DB_PATH))`；`migrate_group_plugin_config` 整体替换为：

```python
def migrate_group_plugin_config():
    """仅表不存在时建表并播种默认群；已有表绝不重播（禁用状态不得因重启复活）。"""
    conn = sqlite3.connect(str(config.DB_PATH))
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name = 'group_plugin_config'"
    ).fetchone()
    if exists:
        conn.close()
        return
    conn.execute("""
        CREATE TABLE IF NOT EXISTS group_plugin_config (
            group_id INTEGER NOT NULL,
            plugin_name TEXT NOT NULL,
            PRIMARY KEY (group_id, plugin_name)
        )
    """)
    rows = [(DEFAULT_GROUP_ID, plugin_key(cls)) for cls in plugin_registry
            if plugin_key(cls) not in SYSTEM_PLUGINS]
    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO group_plugin_config (group_id, plugin_name) VALUES (?, ?)", rows
        )
    conn.commit()
    conn.close()
```

`plugins/group_manager/__init__.py`：3 处（行 13/23/76 附近）`sqlite3.connect("data.db")` → `sqlite3.connect(str(config.DB_PATH))`；文件头部按现有导入风格补 `from core import config`（若已 import config 则仅改连接串）。

- [ ] **Step 4: 测试通过 + 回归**

Run: `python -m pytest test/test_plugin_migrate.py -v` → 2 passed
Run: `python -m pytest -q` → 全绿（333+2）

- [ ] **Step 5: 提交**

```bash
git add core/context.py plugins/group_manager/__init__.py test/test_plugin_migrate.py
git commit -m "fix(插件): 禁用状态重启复活修复与 DB 路径统一"
```

---

### Task 2: webapp/admin 模块（5 端点）+ check 脚本

**Files:**
- Create: `webapp/admin/__init__.py`（空）
- Create: `webapp/admin/app.py`
- Modify: `webapp/app.py`（import + include_router）
- Create: `test/scripts/check_admin_dashboard.py`

**Interfaces:**
- Consumes: `core.config.SUPER_USER/DEFAULT_GROUP_ID/PROJECT_ROOT/DB_PATH/_REQUIRED/CONFIG_PATH`（属性访问）；`core.context.SYSTEM_PLUGINS`（frozenset，无插件依赖，可 import）；`get_current_user_id`
- Produces（Task 3 前端消费）：
  - `GET /api/admin/plugins/scopes` → `{"scopes": [{"group_id": 0, "label": "私聊", "is_default": false}, {"group_id": G, "label": "群 G", "is_default": true}, ...]}`
  - `GET /api/admin/plugins?group_id=N` → `{"group_id": N, "label": "...", "is_default": bool, "plugins": [{"key": str, "enabled": bool, "system": bool}]}`
  - `PUT /api/admin/plugins` `{"group_id": int, "plugin_key": str, "enabled": bool}` → `{"ok": true, "key": ..., "enabled": ...}`；系统插件/未知 key 400
  - `GET /api/admin/config` → `{"yaml": str, "path": "config.yaml", "restart_hint": true}`
  - `PUT /api/admin/config` `{"yaml": str}` → `{"ok": true}` 或 400 `{"detail": "具体原因"}`

- [ ] **Step 1: 写失败 check 脚本**

创建 `test/scripts/check_admin_dashboard.py`（模式照 `check_activities_api.py`；超管=默认配置的 1057613133）：

```python
"""管理仪表盘 API：超管守卫、插件启停、配置校验/备份/原子写。

独立进程运行: python test/scripts/check_admin_dashboard.py
"""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_tmp = tempfile.mkdtemp(prefix="botero_admin_test_")
sys.path.insert(0, str(PROJECT_ROOT / "test" / "scripts"))
from _env import write_config  # noqa: E402

os.environ["BOTERO_CONFIG"] = write_config(_tmp)

from fastapi.testclient import TestClient  # noqa: E402
from core import config  # noqa: E402
from core.auth import make_login_key  # noqa: E402
from webapp.app import app  # noqa: E402

client = TestClient(app)
DB = str(config.DB_PATH)
conn = sqlite3.connect(DB)
from core.database_manager import init_schema  # noqa: E402

init_schema(conn, conn.cursor())
conn.commit()
conn.close()
SH = {"Authorization": "Bearer " + make_login_key(str(config.SUPER_USER[0]))}
JH = {"Content-Type": "application/json", **SH}
OH = {"Authorization": "Bearer " + make_login_key("999")}

def check(name, ok, extra=""):
    global fail
    print(f"{'ok' if ok else 'FAIL'} - {name}" + (f" {extra}" if extra else ""))
    if not ok:
        fail += 1

fail = 0

# —— 超管守卫 ——
for method, path in [("get", "/api/admin/plugins/scopes"), ("get", "/api/admin/plugins?group_id=0"),
                     ("get", "/api/admin/config")]:
    r = getattr(client, method)(path)
    check(f"非超管 {path.split('?')[0]} 403", r.status_code == 403)
r = client.put("/api/admin/plugins", headers={"Content-Type": "application/json", **OH},
               json={"group_id": 0, "plugin_key": "dice", "enabled": True})
check("非超管 PUT 插件 403", r.status_code == 403)
r = client.put("/api/admin/config", headers={"Content-Type": "application/json", **OH}, json={"yaml": "x: 1"})
check("非超管 PUT 配置 403", r.status_code == 403)

# —— 范围与插件列表 ——
r = client.get("/api/admin/plugins/scopes", headers=SH)
scopes = r.json().get("scopes", [])
check("scopes 200 含私聊", r.status_code == 200 and any(s["group_id"] == 0 for s in scopes))
check("scopes 含默认群且标注", any(s["group_id"] == config.DEFAULT_GROUP_ID and s["is_default"] for s in scopes))

r = client.get(f"/api/admin/plugins?group_id={config.DEFAULT_GROUP_ID}", headers=SH)
data = r.json()
check("插件列表 200 且非空", r.status_code == 200 and len(data["plugins"]) > 0)
system_keys = {p["key"] for p in data["plugins"] if p["system"]}
check("系统插件被标记", len(system_keys) > 0 and "menu" in system_keys)
check("列表含常规插件", any(p["key"] == "dice" and not p["system"] for p in data["plugins"]))

# —— toggle ——
r = client.put("/api/admin/plugins", headers=JH,
               json={"group_id": 777, "plugin_key": "dice", "enabled": False})
check("禁用写库", r.status_code == 200)
c = sqlite3.connect(DB)
row = c.execute("SELECT 1 FROM group_plugin_config WHERE group_id=777 AND plugin_name='dice'").fetchone()
c.close()
check("禁用=删行", row is None)
r = client.get("/api/admin/plugins?group_id=777", headers=SH)
check("禁用后列表反映", next(p for p in r.json()["plugins"] if p["key"] == "dice")["enabled"] is False)
r = client.put("/api/admin/plugins", headers=JH,
               json={"group_id": 777, "plugin_key": "dice", "enabled": True})
c = sqlite3.connect(DB)
row = c.execute("SELECT 1 FROM group_plugin_config WHERE group_id=777 AND plugin_name='dice'").fetchone()
c.close()
check("启用=有行", row is not None)
r = client.put("/api/admin/plugins", headers=JH,
               json={"group_id": 777, "plugin_key": "menu", "enabled": False})
check("系统插件 400", r.status_code == 400)
r = client.put("/api/admin/plugins", headers=JH,
               json={"group_id": 777, "plugin_key": "no_such_plugin", "enabled": True})
check("未知插件 400", r.status_code == 400)

# —— 配置读取与校验写 ——
r = client.get("/api/admin/config", headers=SH)
orig = open(config.CONFIG_PATH, encoding="utf-8").read()
check("config GET 与磁盘一致", r.status_code == 200 and r.json()["yaml"] == orig)

bad_cases = [
    ("坏缩进", "bot: [unclosed"),
    ("非 dict 顶层", "- a\n- b"),
    ("缺必填", "bot:\n  qq: \"1\"\n"),
]
for name, payload in bad_cases:
    r = client.put("/api/admin/config", headers=JH, json={"yaml": payload})
    unchanged = open(config.CONFIG_PATH, encoding="utf-8").read() == orig
    check(f"非法配置 400 且不落盘（{name}）", r.status_code == 400 and unchanged, r.text[:80])

valid = orig + "\n# web edit test marker\n"
r = client.put("/api/admin/config", headers=JH, json={"yaml": valid})
bak = Path(str(config.CONFIG_PATH) + ".bak")
check("合法保存 200", r.status_code == 200, r.text[:80])
check("文件已更新", open(config.CONFIG_PATH, encoding="utf-8").read() == valid)
check("备份生成且为旧内容", bak.is_file() and bak.read_text(encoding="utf-8") == orig)
r = client.get("/api/admin/config", headers=SH)
check("保存后回读一致", r.json()["yaml"] == valid)

print(f"\n{'ALL PASS' if fail == 0 else f'{fail} FAILED'}")
sys.exit(1 if fail else 0)
```

- [ ] **Step 2: 运行确认失败**

Run: `python -X utf8 test/scripts/check_admin_dashboard.py`
Expected: 全部 FAIL（路由 404/405）

- [ ] **Step 3: 实现 `webapp/admin/app.py`**

```python
"""管理仪表盘子应用：插件启停与配置编辑（仅超级用户）。"""

import os
import shutil
import sqlite3
from typing import Annotated

import yaml
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core import config
from core.context import SYSTEM_PLUGINS
from core.web.auth_deps import get_current_user_id
from webapp import STATIC_DIR

router = APIRouter()


def _require_super(user_id: str) -> None:
    if int(user_id) not in config.SUPER_USER:
        raise HTTPException(status_code=403, detail="仅超级用户")


def _plugin_keys() -> set[str]:
    """文件系统枚举 plugins/（包目录 + 裸 .py）；webapp 不 import plugins。"""
    root = config.PROJECT_ROOT / "plugins"
    keys = set()
    if root.is_dir():
        for p in sorted(root.iterdir()):
            if p.name.startswith("__"):
                continue
            if p.is_dir() and (p / "__init__.py").is_file():
                keys.add(p.name)
            elif p.is_file() and p.suffix == ".py":
                keys.add(p.stem)
    return keys


def _scope_label(gid: int) -> str:
    return "私聊" if gid == 0 else f"群 {gid}"


def _enabled_set(gid: int) -> set[str]:
    conn = sqlite3.connect(str(config.DB_PATH))
    rows = conn.execute(
        "SELECT plugin_name FROM group_plugin_config WHERE group_id = ?", (int(gid),)
    ).fetchall()
    conn.close()
    return {r[0] for r in rows}


class PluginToggleIn(BaseModel):
    group_id: int = Field(ge=0)
    plugin_key: str = Field(min_length=1, max_length=100)
    enabled: bool


class ConfigIn(BaseModel):
    yaml: str = Field(min_length=1)


@router.get("/api/admin/plugins/scopes")
def api_admin_scopes(user_id: Annotated[str, Depends(get_current_user_id)]):
    _require_super(user_id)
    conn = sqlite3.connect(str(config.DB_PATH))
    gids = [r[0] for r in conn.execute(
        "SELECT DISTINCT group_id FROM group_plugin_config").fetchall()]
    conn.close()
    seen = {0, config.DEFAULT_GROUP_ID, *gids}
    scopes = [
        {"group_id": g, "label": _scope_label(g), "is_default": g == config.DEFAULT_GROUP_ID}
        for g in sorted(seen)
    ]
    return {"scopes": scopes}


@router.get("/api/admin/plugins")
def api_admin_plugins(group_id: int, user_id: Annotated[str, Depends(get_current_user_id)]):
    _require_super(user_id)
    enabled = _enabled_set(group_id)
    plugins = [
        {"key": k, "enabled": k in enabled, "system": k in SYSTEM_PLUGINS}
        for k in sorted(_plugin_keys())
    ]
    return {"group_id": group_id, "label": _scope_label(group_id),
            "is_default": group_id == config.DEFAULT_GROUP_ID, "plugins": plugins}


@router.put("/api/admin/plugins")
def api_admin_toggle(body: PluginToggleIn, user_id: Annotated[str, Depends(get_current_user_id)]):
    _require_super(user_id)
    if body.plugin_key in SYSTEM_PLUGINS:
        raise HTTPException(status_code=400, detail="系统插件不可禁用")
    if body.plugin_key not in _plugin_keys():
        raise HTTPException(status_code=400, detail=f"插件不存在：{body.plugin_key}")
    conn = sqlite3.connect(str(config.DB_PATH))
    if body.enabled:
        conn.execute(
            "INSERT OR IGNORE INTO group_plugin_config (group_id, plugin_name) VALUES (?, ?)",
            (body.group_id, body.plugin_key),
        )
    else:
        conn.execute(
            "DELETE FROM group_plugin_config WHERE group_id = ? AND plugin_name = ?",
            (body.group_id, body.plugin_key),
        )
    conn.commit()
    conn.close()
    return {"ok": True, "key": body.plugin_key, "enabled": body.enabled}


def _validate_config(text: str) -> None:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"YAML 解析失败：{exc}") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="配置顶层必须是键值映射")
    for dotted in config._REQUIRED:
        section, _, key = dotted.partition(".")
        value = (data.get(section) or {}).get(key)
        if value is None or value == "" or value == []:
            raise HTTPException(status_code=400, detail=f"缺少必填配置项 {dotted}")


@router.get("/api/admin/config")
def api_admin_config_get(user_id: Annotated[str, Depends(get_current_user_id)]):
    _require_super(user_id)
    text = config.CONFIG_PATH.read_text(encoding="utf-8")
    return {"yaml": text, "path": config.CONFIG_PATH.name, "restart_hint": True}


@router.put("/api/admin/config")
def api_admin_config_put(body: ConfigIn, user_id: Annotated[str, Depends(get_current_user_id)]):
    _require_super(user_id)
    _validate_config(body.yaml)
    path = config.CONFIG_PATH
    if path.is_file():
        shutil.copyfile(path, Path(str(path) + ".bak"))
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(body.yaml, encoding="utf-8")
    os.replace(tmp, path)
    return {"ok": True}


from pathlib import Path  # noqa: E402  (置底避免与顶部风格冲突——实现时并入顶部 import 区)
```

（实现时把 `from pathlib import Path` 并入顶部 import，删除置底行。）

`webapp/app.py`：`from webapp.admin.app import router as admin_router`（按现有字母序插入 import 区）+ `app.include_router(admin_router)`（include 区末尾追加）。

`webapp/admin/__init__.py`：空文件。

- [ ] **Step 4: 运行 check 通过**

Run: `python -X utf8 test/scripts/check_admin_dashboard.py` → ALL PASS

- [ ] **Step 5: 回归 + 提交**

Run: `python -m pytest test/test_webapp_api_suites.py -q` → 通过

```bash
git add webapp/admin/__init__.py webapp/admin/app.py webapp/app.py test/scripts/check_admin_dashboard.py
git commit -m "feat(管理): 插件启停与配置编辑 API"
```

---

### Task 3: 前端 admin 三件套 + 导航入口

**Files:**
- Create: `webapp/static/admin.html` / `admin.css` / `admin.js`
- Modify: `core/web/static/nav.js`（NAV_ITEMS 加「管理」→ `/admin`，放在「工具箱」后）
- Create: `test/test_admin_render.js`

**Interfaces:**
- Consumes: Task 2 五端点；`/shared/auth.js` GalleryAuth；既有 base.css/profile.css 样式变量
- Produces: `/admin` 页面（Task 3 内自带页面路由——见 admin/app.py 追加）

- [ ] **Step 1: admin/app.py 追加页面路由**（并入 Task 2 文件，本任务提交）

```python
@router.get("/admin")
def admin_page():
    page = STATIC_DIR / "admin.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="缺少静态页面")
    return FileResponse(page)
```

- [ ] **Step 2: 写 admin.html（结构照 schedule.html：导航/登录框/main）**

关键差异：`<main id="adminMain">`；标题「管理仪表盘」；两节容器由 JS 渲染。样式引 `base.css`/`profile.css`/`admin.css`；脚本引 auth/motion/nav + `/static/admin.js`。

- [ ] **Step 3: 写 admin.css**

```css
/* 管理仪表盘 */
.admin-section { margin-top: 1.2rem; }
.admin-row {
  display: flex; align-items: center; gap: 0.6rem;
  padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--rule);
}
.admin-key { flex: 1; font-size: 0.9rem; }
.admin-badge { font-size: 0.75rem; color: var(--ink-soft); }
.admin-toggle {
  border: 1px solid var(--accent); background: var(--accent-soft);
  color: var(--accent-ink); border-radius: 999px; padding: 0.2rem 0.9rem;
  font: inherit; font-size: 0.8rem; cursor: pointer;
}
.admin-toggle.off { background: transparent; color: var(--ink-soft); }
.admin-toggle:disabled { opacity: 0.5; cursor: default; }
.admin-config {
  width: 100%; box-sizing: border-box; min-height: 24rem;
  font-family: Consolas, "Courier New", monospace; font-size: 0.82rem;
  padding: 0.75rem; border: 1px solid var(--rule); border-radius: 8px;
  background: var(--paper-card); color: var(--ink); white-space: pre;
  overflow-x: auto;
}
.admin-hint { color: var(--ink-soft); font-size: 0.8rem; }
.admin-error { color: #b3402f; font-size: 0.82rem; white-space: pre-wrap; }
```

- [ ] **Step 4: 写 admin.js**

```javascript
const adminMain = document.getElementById("adminMain");

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

async function api(path, options = {}) {
  const res = await fetch(path, { headers: GalleryAuth.headers(), ...options });
  if (res.status === 403) throw new Error("仅超级用户");
  if (res.status === 401) { GalleryAuth.clear(); location.href = "/login?next=/admin"; throw new Error("未登录"); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "请求失败");
  return data;
}

async function boot() {
  adminMain.innerHTML = "<p class='loading-msg'>加载中…</p>";
  try {
    await api("/api/admin/plugins/scopes");  // 权限探测
  } catch (err) {
    adminMain.innerHTML = `<p class='empty-hint center'>${escapeHtml(err.message)}</p>`;
    return;
  }
  renderSkeleton();
  await Promise.all([loadScopes(), loadConfig()]);
}

function renderSkeleton() {
  adminMain.innerHTML = `
    <section class="settings-section admin-section">
      <h2>插件管理</h2>
      <p class="admin-hint">改动即时生效（bot 每次事件实时读取）；私聊=仅私聊消息生效的插件范围。</p>
      <label class="alarm-field"><span class="alarm-field-label">作用范围</span>
        <select id="scopeSelect" class="alarm-input"></select></label>
      <div id="pluginList"></div>
    </section>
    <section class="settings-section admin-section">
      <h2>配置文件</h2>
      <p class="admin-hint">保存后需重启 bot 与 webapp 进程生效；保存前自动备份为 config.yaml.bak（保留一代）。</p>
      <textarea id="configArea" class="admin-config" spellcheck="false"></textarea>
      <div class="submit-row">
        <button type="button" id="configSave" class="admin-toggle">保存配置</button>
        <span id="configHint" class="admin-hint"></span>
      </div>
      <p id="configError" class="admin-error hidden"></p>
    </section>`;
  document.getElementById("scopeSelect").addEventListener("change", (e) => loadPlugins(Number(e.target.value)));
  document.getElementById("configSave").addEventListener("click", saveConfig);
}

async function loadScopes() {
  const data = await api("/api/admin/plugins/scopes");
  const sel = document.getElementById("scopeSelect");
  sel.innerHTML = "";
  data.scopes.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s.group_id;
    opt.textContent = s.label + (s.is_default ? "（默认）" : "");
    sel.appendChild(opt);
  });
  if (data.scopes.length) await loadPlugins(data.scopes[0].group_id);
}

async function loadPlugins(gid) {
  const host = document.getElementById("pluginList");
  host.innerHTML = "<p class='admin-hint'>加载中…</p>";
  const data = await api(`/api/admin/plugins?group_id=${gid}`);
  const sys = data.plugins.filter((p) => p.system);
  const normal = data.plugins.filter((p) => !p.system);
  host.innerHTML = "";
  normal.forEach((p) => host.appendChild(pluginRow(p, gid)));
  const lockTitle = document.createElement("p");
  lockTitle.className = "admin-hint";
  lockTitle.textContent = "🔒 系统插件（恒启用，不可修改）";
  host.appendChild(lockTitle);
  sys.forEach((p) => {
    const row = pluginRow(p, gid);
    row.querySelector("button").disabled = true;
    host.appendChild(row);
  });
}

function pluginRow(p, gid) {
  const row = document.createElement("div");
  row.className = "admin-row";
  const key = document.createElement("span");
  key.className = "admin-key";
  key.textContent = p.key;
  const badge = document.createElement("span");
  badge.className = "admin-badge";
  badge.textContent = p.enabled ? "✅ 启用" : "❌ 禁用";
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "admin-toggle" + (p.enabled ? "" : " off");
  btn.textContent = p.enabled ? "禁用" : "启用";
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    try {
      await api("/api/admin/plugins", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ group_id: gid, plugin_key: p.key, enabled: !p.enabled }),
      });
      await loadPlugins(gid);
    } catch (err) {
      alert(err.message);
      btn.disabled = false;
    }
  });
  row.append(key, badge, btn);
  return row;
}

async function loadConfig() {
  const data = await api("/api/admin/config");
  document.getElementById("configArea").value = data.yaml;
}

async function saveConfig() {
  const btn = document.getElementById("configSave");
  const hint = document.getElementById("configHint");
  const errEl = document.getElementById("configError");
  errEl.classList.add("hidden");
  btn.disabled = true;
  try {
    await api("/api/admin/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ yaml: document.getElementById("configArea").value }),
    });
    hint.textContent = "已保存（重启进程后生效）";
    await loadConfig();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove("hidden");
  } finally {
    btn.disabled = false;
  }
}

GalleryAuth.refreshMe().finally(() => { GalleryAuth.renderAuth(document.getElementById("authArea")); boot(); });
```

（`alarm-field/alarm-field-label/alarm-input/submit-row` 复用 schedule.css 类——admin.html 需同时引 `schedule.css`，或把这几个类复制进 admin.css；实现时选择**引 schedule.css**（零拷贝）。）

- [ ] **Step 5: node DOM 测试 `test/test_admin_render.js`**

stub 模式照 `test_schedule_render.js`：fetch 桩返回 scopes（私聊+默认群）、plugins（dice 普通 + menu 系统）、config 原文；断言：范围下拉 2 项且默认群带「（默认）」；普通插件行 toggle 按钮存在、系统插件按钮 disabled；点 toggle 发出 PUT（fetch 记录断言 method/body）；textarea 值等于桩配置；点保存发出 PUT config；403 场景（scopes 桩返回 403）显示「仅超级用户」。约 8 断言。

- [ ] **Step 6: 运行**

Run: `node test/test_admin_render.js` → 全 ok
Run: `python -m pytest test/test_dom_render_suites.py -q` → 通过

- [ ] **Step 7: 提交**

```bash
git add webapp/static/admin.html webapp/static/admin.css webapp/static/admin.js webapp/admin/app.py core/web/static/nav.js test/test_admin_render.js
git commit -m "feat(管理): 仪表盘页面与导航入口"
```

---

### Task 4: 文档、版本与全量回归

**Files:**
- Modify: `CHANGELOG.md`、`core/config.py`、`specs/web-gallery.md`、`AGENTS.md`、`CLAUDE.md`

- [ ] **Step 1: 版本与 CHANGELOG**

`BOTERO_VERSION = "1.36.0"`；CHANGELOG `[未发布]` 前插入：

```markdown
## [1.36.0] - 2026-09-02

### 新增

- **管理仪表盘**：新页面 `/admin`（仅超级用户）——按群/私聊查看并修改插件启停（改动即时生效，系统插件锁定）；config.yaml 在线编辑（保存前自动校验必填项与 YAML 语法、自动备份 `.bak`、原子写盘，保存后需重启进程生效）。导航新增「管理」入口

### 修复

- **插件禁用重启复活**：bot 启动不再对已有配置表重新播种默认群，网页/QQ 端禁用的插件重启后保持禁用
- **硬编码 data.db**：插件启停读取与群管理改走 `config.yaml` 配置的数据库路径
```

- [ ] **Step 2: specs 与入口文档**

- `specs/web-gallery.md`：模块数 11→12（首段、模块表加 `| 管理 | admin | /admin | 插件启停+配置编辑（超管） |`、路由 include、页面清单）；新增 `### 管理（admin 模块）` API 小节（5 端点表 + 超管守卫说明）
- `AGENTS.md`：两处「11 个模块」→「12 个模块」，模块清单补 `admin`
- `CLAUDE.md`：同样「11」→「12」三处 + 模块清单补 `webapp/admin/`

- [ ] **Step 3: 全量回归 + 提交**

Run: `python -m pytest` → 全绿；`node test/test_admin_render.js` ok

```bash
git add CHANGELOG.md core/config.py specs/web-gallery.md AGENTS.md CLAUDE.md
git commit -m "docs(管理): 仪表盘版本与模块文档收尾"
```

---

## 自审记录

- **Spec 覆盖**：D1→Task 3；D2→Task 2；D3→Task 2（`_validate_config` 三步序）；D4→Task 2（scopes/枚举）；D5→Task 2 守卫 + Task 3 导航/页内提示；D6→Task 1；D7 未越界。
- **占位符扫描**：Task 3 Step 2（html 骨架文字描述+差异点）与 Step 5（node 测试断言清单）为规格化描述而非全文代码——html 骨架以 schedule.html 为模板逐点替换，node 测试以 test_schedule_render.js 为模板按断言清单落写；其余代码块完整。
- **类型一致性**：scopes/plugins/config 三响应形状在 Task 2（实现）、Task 3（fetch 消费）、check/node 桩三处一致；`_REQUIRED` 引用自 core.config（含下划线私有名——spec D3 已确认复用，避免复制清单漂移）。
- **测试隔离**：check 脚本 `write_config` 临时配置（config 读写都落在临时文件，`.bak` 亦然）；`_plugin_keys` 枚举真实仓库 plugins/ 目录（只读，无害）。
- **Task 1 Step 2 注记**：测试进程 plugin_registry 为空导致「禁用不复活」用例需注入假类才可红——已在该步骤内写明注入法并以注入版为准。
