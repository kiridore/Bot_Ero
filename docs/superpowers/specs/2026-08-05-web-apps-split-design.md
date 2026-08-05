# 打卡图库功能拆分设计（多子应用 + 子域名）

**日期:** 2026-08-05
**状态:** 已确认（逐节评审通过）

## 1. 背景与目标

`checkin_gallery/` 目前是单进程 FastAPI 应用，822 行 `app.py` 聚合 9 个功能域（图库、个人主页、打卡、商店、闹钟、留言簿、活动、跑团车卡、设置+称号），页面导航互相交错。目标：按功能域拆分为多个独立运行的子应用，各自子域名，由导航主页（`homepage/`）聚合入口。

**成功标准：**
- 每个子应用可独立启动/停止/更新，互不影响
- 任一子应用崩溃不影响其他域
- 导航主页成为唯一入口（旧链接不做兼容，直接失效）
- 共享逻辑单份维护（core/），无复制粘贴

## 2. 目标架构

### 2.1 拓扑

```
                        ┌─ gallery.littlero.com ─────→ gallery/   (端口 8765, 保留现域名)
                        ├─ profile.littlero.com ────→ profile/   (8767)
                        ├─ trpg.littlero.com ───────→ trpg/      (8768)
 用户 → 导航主页(homepage) ├─ guestbook.littlero.com → guestbook/ (8766, 试点)
 (Caddy 静态托管)         ├─ alarms.littlero.com ───→ alarms/    (8769)
                        └─ activities.littlero.com → activities/ (8770)
```

旧路径（`/profile/*`、`/guestbook`、`/archive*`、`/trpg/*`）**不做重定向，直接失效**。

### 2.2 目录结构（方案 A：共享层上移 + 子应用薄层）

```
core/       ← 共享层（bot 与全部子应用共同依赖）
gallery/    ← 图库（瀑布流 + 认证）
profile/    ← 个人中心（主页/打卡/商店/称号/设置，5 域合一）
trpg/       ← 跑团（车卡）
guestbook/  ← 留言簿（试点）
alarms/     ← 闹钟
activities/ ← 活动
homepage/   ← 导航主页（已有）
plugins/    ← bot（不变）
```

### 2.3 子应用统一结构

每个子应用目录：
```
<domain>/
├── __init__.py
├── __main__.py        ← uvicorn 入口（PORT 默认值各异，env 可覆盖）
├── app.py             ← FastAPI 实例 + 域内路由
└── static/            ← 域内页面（登录用共享 core/web/static/auth.js）
```

### 2.4 域名分配

| 子应用 | 子域名 | 端口 | 内容 |
|---|---|---|---|
| 图库 | gallery.littlero.com（保留现域名） | 8765 | 瀑布流、/thumb /media、/api/checkins /api/users、认证路由 |
| 个人中心 | profile.littlero.com | 8767 | 个人主页、打卡、商店、称号设置、隐私设置 |
| 跑团 | trpg.littlero.com | 8768 | 车卡 CRUD、角色查看、规则 |
| 留言簿 | guestbook.littlero.com | 8766 | 留言列表/发布/点赞（试点） |
| 闹钟 | alarms.littlero.com | 8769 | 闹钟 CRUD |
| 活动 | activities.littlero.com | 8770 | 活动归档列表/详情/媒体 |

## 3. 共享层设计（core/ 增改）

### 3.1 `core/auth.py`（新）

`checkin_gallery/auth.py` 整体搬入：`make_login_key` / `verify_login_key` 接口与实现不变。
- 消除 `plugins/gallery_login_key` → `checkin_gallery` 反向依赖（改 import `core.auth`）
- 所有子应用共享同一 `BOTERO_AUTH_SALT` env，"密钥即 token"模型跨域通用，无 session 迁移

### 3.2 `core/onebot_client.py`（新）

`resolve_display_name` / `resolve_avatar_url`（lru_cache）搬入，全子应用共享昵称/头像缓存。

### 3.3 DB 层统一（改 `core/database_manager.py`）

- `DbManager` 连接路径由相对路径 `"data.db"` 改为共享配置的 DB 路径（消除 cwd 依赖）
- 补 `PRAGMA busy_timeout=5000`（`journal_mode=WAL` 已有）
- 新增 `GuestbookManager`：`list_entries` / `post_entry` / `like_entry`（分页），消灭 guestbook 裸 SQL
- 新增 `ActivityManager`：`list_activities` / `get_activity` / `get_my_activities` / `get_members`，消灭 activity_service 自开 sqlite 连接

### 3.4 `core/title_defs.py`（新）

从 `plugins/title/defs.py` 加载 `TITLE_DEFS` 一次并缓存。
- 消灭 `profile_service` / `checkin_service` / `title_settings` 各自的 importlib 样板
- 消灭 `shop_service`、`title_settings` → `profile_service` 的 service→service 依赖（改为 `core.title_defs`）

### 3.5 共享静态资源 `core/web/static/auth.js`（新）

`checkin_gallery/static/auth.js` 移入。各子应用 `app.mount` 同一目录（不复制）。

### 3.6 配置约定

所有子应用读同一组 `BOTERO_*` 环境变量（DB_PATH / IMAGE_ROOT / ONEBOT_HTTP / ONEBOT_TOKEN / GROUP_ID / AUTH_SALT / 各域专属如 ACTIVITY_ROOT / TRPG_CHARS_ROOT / USER_SETTINGS_ROOT / THUMB_*），PORT 按应用不同默认值。由各 systemd unit 注入。

## 4. 试点：留言簿迁移（guestbook/）

试点理由：最独立、无跨域依赖、仅 3 个 API + 1 页。

### 4.1 新建 `guestbook/` 子应用

- `__main__.py`：uvicorn 入口，PORT 默认 8766
- `app.py`：3 个 API 路由（GET/POST `/api/guestbook`、POST `/api/guestbook/{id}/like`）+ 页面路由 + static mount，逻辑走 `DbManager.guestbook`
- `static/guestbook.html`：从 `checkin_gallery/static/` 移入，登录逻辑引用共享 auth.js
- 删除 `checkin_gallery/guestbook_service.py`（裸 SQL 由 GuestbookManager 替代）

### 4.2 图库主应用瘦身（同一轮）

- `checkin_gallery/app.py`：移除 guestbook 3 个 API 路由、相关 import、`/guestbook` 页面路由
- `checkin_gallery/static/index.html`：移除"留言簿"工具栏链接
- `checkin_gallery/static/profile.html`：导航栏移除"留言簿"项
- 删除 `checkin_gallery/static/guestbook.html` + `guestbook.js`

### 4.3 Caddy 示例（VPS 侧，入文档）

```
guestbook.littlero.com {
    reverse_proxy 127.0.0.1:8766
}
```

### 4.4 导航主页更新

`homepage/entries.json` 新增"留言簿"卡片（badge 可选）。

### 4.5 试点验证清单

1. `guestbook.littlero.com` 可浏览/发布/点赞留言
2. 同一把图库密钥在新域名可登录
3. `grep -r guestbook checkin_gallery/` 无残留引用
4. 机器人进程不受影响（`python main.py` 正常，plugins 用 DbManager 无感知）
5. 导航主页显示留言簿卡片，点击直达

## 5. 其余 5 域迁移模板

试点验收通过后按同一模板逐域推进，一轮一个 commit：

| 步骤 | 内容 |
|---|---|
| 1. 建子应用目录 | `<域>/app.py + __main__.py + static/`，路由从 checkin_gallery/app.py 迁出 |
| 2. 迁 service | 域专属逻辑留子应用内；跨域共享逻辑走 core 共享层 |
| 3. 瘦身主应用 | 移除对应路由/import/导航链接/static 文件 |
| 4. Caddy + systemd | 新子域反代 + 新 systemd unit（示例配置入文档） |
| 5. 导航主页 | entries.json 加卡片 |
| 6. 验证 | 新域名功能回归 + grep 无残留 + 机器人进程不受影响 |

各域归属：
- **图库 gallery/**（8765）：`/thumb` `/media` `/api/checkins` `/api/users` + 认证路由（保留现域名，最后迁移——它是主应用的核心，其余域迁完后图库自然只剩自己的路由）
- **个人中心 profile/**（8767）：个人主页（profile_service）、打卡（checkin_service）、商店（shop_service）、称号设置（title_settings + 隐私 user_settings）——5 域合一，共享积分/称号/商店数据，不拆
- **跑团 trpg/**（8768）：characters CRUD + `/api/trpg/rules` + 角色查看（CharOut/_char_to_out 从 app.py 迁入子应用）
- **闹钟 alarms/**（8769）：alarm_service（importlib 加载 plugins/group_alarm/parser.py 的模式保留）
- **活动 activities/**（8770）：activity_service + `/archive/{id}/media/*`（改用 ActivityManager）

## 6. 部署（systemd + Caddy）

每个子应用一个 systemd unit，示例：

```ini
[Unit]
Description=BotEro guestbook web
After=network.target

[Service]
WorkingDirectory=/opt/BotEro
Environment=BOTERO_GALLERY_PORT=8766
Environment=BOTERO_DB_PATH=/opt/BotEro/data.db
Environment=BOTERO_AUTH_SALT=...
ExecStart=/usr/bin/python3 -m guestbook
Restart=always

[Install]
WantedBy=multi-user.target
```

Caddy 各子域：

```
gallery.littlero.com    { reverse_proxy 127.0.0.1:8765 }
profile.littlero.com    { reverse_proxy 127.0.0.1:8767 }
trpg.littlero.com       { reverse_proxy 127.0.0.1:8768 }
guestbook.littlero.com  { reverse_proxy 127.0.0.1:8766 }
alarms.littlero.com     { reverse_proxy 127.0.0.1:8769 }
activities.littlero.com { reverse_proxy 127.0.0.1:8770 }
```

域名解析：需在 DNS 添加各子域 A 记录（域名侧操作，文档注明；实施在 VPS/Caddy 配置文件）。

## 7. 风险与缓解

| 风险 | 缓解 |
|---|---|
| SQLite 多进程并发写锁 | WAL 已有 + 补 busy_timeout=5000；web 侧写操作低频（打卡/留言/兑换），冲突窗口小 |
| 行为漂移（checkin_service 与 bot 打卡逻辑同源分叉） | 本次只搬文件改 import，不重写逻辑；打卡逻辑重写不在本计划范围 |
| 密钥一致性 | 所有子应用共享 BOTERO_AUTH_SALT env，密钥跨域通用，bot 的 `/图库密钥` 无需改动 |
| 大重构回归 | 渐进式 + 每轮验证清单 + 每轮独立 commit 可回退 |
| 域名解析失败 | 子域 DNS 记录需提前添加（文档注明）；本地测试用 host 或端口直连 |

## 8. 范围外（明确不做）

- 旧链接重定向/兼容
- checkin_service 与 bot 打卡逻辑合并重写
- guestbook/activity 之外的其他裸 SQL 清理（alarm 的 db.cur 裸 SQL 保留现状）
- 数据库拆分（各域独立库）——统一共享 data.db
- 认证体系改造（保持密钥即 token）
