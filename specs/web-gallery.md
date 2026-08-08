# Spec: Web 应用体系（图库/个人中心/跑团/留言簿/闹钟/活动）

> 关联规范: [database.md](database.md) | [conventions.md](conventions.md) | [architecture.md](architecture.md)
> 父文档: [CLAUDE.md](../CLAUDE.md)
> 最后更新: 2026-08-09 (单进程 webapp + 同源路径分区：6 模块路由挂根域 `littlero.tech` 下 `/gallery` 等路径；删除子域、Host 分发与 `BOTERO_GALLERY_URL`)

---

## Constraint: 应用拓扑

Web 端按功能域拆分为 **6 个模块（`gallery`/`guestbook`/`profile`/`trpg`/`alarms`/`activities`）**，全部注册在 **1 个 FastAPI 进程（`webapp`，端口 8765）** 上：每个模块的 `app.py` 导出 `router = APIRouter()`，`webapp/app.py` 统一 include。**单一 origin（根域 `littlero.tech`）按路径分区**：API/静态/媒体在根路径（全局唯一），页面在 `/gallery` `/guestbook` `/profile` `/trpg` `/alarms` `/activities` 等前缀路径；根域 `/` 由 webapp 提供导航主页（`webapp/homepage/`，纯静态 + `entries.json` 配置卡片）聚合入口。

| 模块 | 包 | 路径分区 | 职责 |
|------|------|------|------|
| 图库 | `gallery` | `/gallery` | 打卡图库瀑布流 + /thumb /media + 打卡数据 API |
| 留言簿 | `guestbook` | `/guestbook` | 留言列表/发表/点赞 |
| 个人中心 | `profile` | `/profile`（`/profile/checkin` `/profile/shop` `/profile/settings`） | 个人主页/打卡/商店/称号/设置 5 域聚合 |
| 跑团 | `trpg` | `/trpg`（`/trpg/char/{user_id}/{char_id}`） | 车卡创建/编辑/查看 |
| 闹钟 | `alarms` | `/alarms` | 闹钟 CRUD |
| 活动 | `activities` | `/activities`（`/activities/{activity_id}`） | 活动归档/详情 |

```
┌─────────────────────┐     ┌──────────────────────────────────────────┐
│  main.py (bot)       │     │  webapp (单进程, 127.0.0.1:8765)          │
│  ws://127.0.0.1:3001 │     │  /gallery /guestbook /profile /trpg       │
│                      │     │  /alarms /activities（6 个 APIRouter）     │
└────────┬────────────┘     │        │  └─ Caddy 全量反代              │
         │                  │        └── / (webapp/homepage 导航主页)   │
         └──────────┬───────┘
                    │
              ┌─────▼─────┐
              │  data.db   │  (共享 SQLite，WAL；webapp 经 core 访问)
              └───────────┘
```

**启动:** `python -m webapp [--host HOST] [--port PORT]`（默认端口 8765；`--db`/`--images` 覆盖数据库/图片目录）。

**MUST NOT:** 旧子域 URL（`https://gallery.littlero.tech` 等）与旧单体路径不提供重定向，直接失效；模块之间不互相内链页面路径，同源引用一律用根相对路径（`/gallery` 等）。

**MUST NOT:** 给 uvicorn 加 `--workers` 多进程 worker（多 worker 重新引入多进程 SQLite 写竞争）。

---

## Constraint: 共享层（`core/`）

子应用与 bot 共用同一 `core/` 包，**MUST NOT** 在子应用内复制共享逻辑：

| 模块 | 职责 |
|------|------|
| `core/config.py` | 全部 `BOTERO_*` 环境变量读取（bot 与 Web 唯一来源）；`webapp/gallery/config.py` 为兼容再导出层 |
| `core/auth.py` | `make_login_key` / `verify_login_key`（HMAC 登录密钥） |
| `core/web/auth_deps.py` | `get_current_user_id` / `get_optional_user_id`（登录依赖注入，唯一权威副本；feature 模块一律从本模块 import，**MUST NOT** 各自复制） |
| `core/onebot_client.py` | `resolve_display_name` / `resolve_avatar_url`（QQ 昵称/头像） |
| `core/title_defs.py` | `TITLE_DEFS` 加载 |
| `core/database_manager.py` + `core/db/` | `DbManager` 统一数据库访问（WAL + busy_timeout=5000；checkin/points/shop/lottery/titles/alarm/immortal/quest/activity/guestbook 各业务 manager） |
| `core/character_store.py` / `core/user_settings.py` | 角色卡/个人设置 JSON 存储（原子写 tmp + os.replace） |
| `core/trpg/` | 跑团规则与角色派生计算 |
| `core/web/static/` | 共享静态（auth.js / gallery.css / profile.css），各子应用以 `/shared` 挂载同一目录，**MUST NOT** 复制 |

- Constraint: 全部子应用样式必须经由 `core/web/static/gallery.css` 的 `:root` token（报纸风数值，与 webapp/homepage/style.css 同步），禁止在子应用样式文件引入新的硬编码颜色。

---

## Constraint: 模块统一骨架

每个功能域模块目录（位于 `webapp/` 包内）：`app.py`（`router = APIRouter()`，业务/页面路由）、`__init__.py`；静态文件全部集中在 `webapp/static/`（25 个文件，文件名全局唯一）。单进程入口 `webapp/app.py` 负责认证路由、导航主页（`webapp/homepage/`，根路径 `/` 与 5 个资源路由）、router include 与静态挂载：

```python
# webapp/app.py（唯一 FastAPI 入口）
app = FastAPI(title="BotEro Web", version="1.0.0")
# POST /api/auth/login + GET /api/auth/me（唯一一份）
# GET / → webapp/homepage/index.html（导航主页，entries/quotes/notices JSON 同根路径）
app.include_router(gallery_router)       # from webapp.gallery.app import router as ...
app.include_router(guestbook_router)
app.include_router(profile_router)
app.include_router(trpg_router)
app.include_router(alarms_router)
app.include_router(activities_router)    # 最后：/activities/{activity_id:int} 不遮蔽任何已注册路由
app.mount("/static", StaticFiles(directory=webapp/static))    # 全部模块静态
app.mount("/shared", StaticFiles(directory=core/web/static))  # 共享静态

# 认证助手（基于 core.auth.verify_login_key，唯一权威副本在 core/web/auth_deps.py）
user_id = Depends(get_current_user_id)     # 必须登录，否则 401
user_id = Depends(get_optional_user_id)    # 可选登录（公开+登录混合路由）
```

- **MUST:** 认证路由（`POST /api/auth/login`、`GET /api/auth/me`）只允许存在于 `webapp/app.py`，feature 模块**不得**再定义
- **MUST:** 每个模块的 `app.py` 导出 `router = APIRouter()`，不得创建 `FastAPI()` 实例、不得 mount 静态目录
- 页面路由用 `FileResponse` 返回 `webapp/static/*.html`；页面路径带分区前缀（`/gallery` 等），API 保持根路径
- `profile` 依赖 `webapp.gallery.repository`（2 处 import：`CheckinImage`、`fetch_user_settlement_day`）——图库数据层是个人中心的数据来源

---

## Constraint: 配置

所有配置通过环境变量读取（`core/config.py`，单一来源）：

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `BOTERO_DB_PATH` | `data.db` | 数据库路径 |
| `BOTERO_IMAGE_ROOT` | `server_data/record_images` | 打卡图片目录 |
| `BOTERO_GALLERY_HOST` | `0.0.0.0` | 绑定地址（局域网可访问；仅本机用 `127.0.0.1`） |
| `BOTERO_GALLERY_PORT` | `8765` | webapp 监听端口（唯一端口） |
| `BOTERO_ONEBOT_HTTP` | `http://192.168.0.103:3000` | OneBot HTTP API |
| `BOTERO_ONEBOT_TOKEN` | `123456` | OneBot HTTP 令牌 |
| `BOTERO_GROUP_ID` | `296470819` | 默认群号（昵称查询） |
| `BOTERO_THUMB_CACHE` | `server_data/thumb_cache` | 缩略图缓存目录 |
| `BOTERO_THUMB_MAX_WIDTH` | `480` | 缩略图最大宽度 |
| `BOTERO_THUMB_MAX_HEIGHT` | `720` | 缩略图最大高度 |
| `BOTERO_THUMB_QUALITY` | `82` | JPEG 缩略图质量 |
| `BOTERO_AUTH_SALT` | `BotEro-Gallery-ChangeMe` | HMAC 盐值（**单一来源 `scripts/botero.env`**，bot 与 webapp 共用；生产建议改随机值） |
| `BOTERO_CHECKIN_MAX_IMAGES` | `9` | 单次打卡最大图片数 |
| `BOTERO_CHECKIN_MAX_BYTES` | `10485760` (10MB) | 单张图片最大字节 |
| `BOTERO_TRPG_CHARS_ROOT` | `server_data/trpg_chars` | 跑团角色卡 JSON 存储根目录 |
| `BOTERO_USER_SETTINGS_ROOT` | `server_data/user_settings` | 个人设置 JSON 存储根目录 |
| `BOTERO_ACTIVITY_ROOT` | `server_data/activity_archive` | 活动归档根目录（`<活动id>/` 子目录） |

---

## Constraint: 数据库共享

所有子应用与 bot 共用同一 SQLite（`BOTERO_DB_PATH`），**MUST** 通过 `core.database_manager.DbManager` 访问：

- 连接开启 WAL 模式，`busy_timeout=5000`（多进程并发安全）
- 子应用**只允许**经由 `core/db/*` 业务 manager 读写，不直接裸 SQL（`webapp/gallery/repository.py` 是图库只读查询的既有例外）
- `REMEDY_MARKER = "remedy_checkin"`：查询打卡数据时**必须**排除 `content = "remedy_checkin"` 的记录

---

## Constraint: HMAC 认证（密钥即 token）

```python
# 登录密钥生成（core.auth.make_login_key，QQ 插件 gallery_login_key 调用）:
key = make_login_key(user_id)  # HMAC-SHA256(user_id, AUTH_SALT)[:12] → Base64 载荷

# 验证（core.auth.verify_login_key，各子应用共享）:
user_id = verify_login_key(key)  # 返回 user_id 字符串或 None
```

**登录模型:**
- 密钥即 token：`Authorization: Bearer <key>` 传输，无服务端 session
- 全站共享同一 `BOTERO_AUTH_SALT`，同一密钥在所有分区通用；**盐值单一来源为 `scripts/botero.env`**（bot 生成密钥与 webapp 验证密钥共用，改盐只改该文件）
- 前端 token 存 localStorage（**单 origin 共享**——任一分区登录后其余分区免重复登录；`core/web/static/auth.js` 同时保留根域 cookie 写入，兼容旧缓存）
- **依赖注入:** `Depends(get_current_user_id)`（必须登录）/ `Depends(get_optional_user_id)`（可选登录），定义在 `core/web/auth_deps.py`

---

## Constraint: API 路由（按模块归属）

### 认证（唯一一份，`webapp/app.py`）

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `POST` | `/api/auth/login` | 否 | 登录，返回 token |
| `GET` | `/api/auth/me` | 必须 | 当前用户信息 |

### 图库（`gallery` 模块）

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/api/checkins` | 可选 | 分页打卡图片列表 |
| `GET` | `/api/users` | 可选 | 所有有打卡记录的用户列表 |
| `GET` | `/thumb/{user_id}/{filename}` | 否 | 缩略图（缺失时生成，缓存到 `THUMB_CACHE`） |
| `GET` | `/media/{user_id}/{filename}` | 否 | 原图 |

### 个人中心（`profile` 模块）

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/api/me/day` | 必须 | 某结算日的打卡详情 |
| `GET` | `/api/me/profile` | 必须 | 用户档案（热度图、称号） |
| `GET` | `/api/me/checkin/status` | 必须 | 本周打卡状态 |
| `POST` | `/api/me/checkin` | 必须 | 网页端打卡上传（multipart） |
| `GET` | `/api/me/shop` | 必须 | 商店货架 |
| `POST` | `/api/me/shop/redeem` | 必须 | 兑换商品 |
| `GET` | `/api/me/titles/settings` | 必须 | 称号设置 |
| `PUT` | `/api/me/titles/equipped` | 必须 | 批量设置装备 |
| `POST` | `/api/me/titles/equip` | 必须 | 装备单个称号 |
| `DELETE` | `/api/me/titles/equipped` | 必须 | 卸下全部 |
| `DELETE` | `/api/me/titles/equip/{id}` | 必须 | 卸下单个 |
| `GET` | `/api/me/settings` | 必须 | 我的个人设置 |
| `PUT` | `/api/me/settings` | 必须 | 更新个人设置（深合并） |

### 跑团（`trpg` 模块）

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/api/me/characters` | 必须 | 我的角色列表（含 current_id） |
| `POST` | `/api/me/characters` | 必须 | 创建角色（服务端计算 hp/ac） |
| `GET` | `/api/me/characters/{char_id}` | 必须 | 我的角色详情 |
| `PUT` | `/api/me/characters/{char_id}` | 必须 | 更新角色 |
| `DELETE` | `/api/me/characters/{char_id}` | 必须 | 删除角色 |
| `POST` | `/api/me/characters/{char_id}/activate` | 必须 | 设为当前角色 |
| `GET` | `/api/characters/{user_id}/{char_id}` | 必须 | 查看他人角色（他人未公开 → 403） |
| `GET` | `/api/trpg/rules` | 否 | DND5E 规则数据（属性/技能/种族/职业/购点） |

### 留言簿（`guestbook` 模块）

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/api/guestbook` | 可选 | 留言列表 |
| `POST` | `/api/guestbook` | 必须 | 发表留言 |
| `POST` | `/api/guestbook/{id}/like` | 必须 | 点赞 |

### 闹钟（`alarms` 模块）

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/api/me/alarms` | 必须 | 闹钟列表 |
| `POST` | `/api/me/alarms` | 必须 | 创建闹钟 |
| `DELETE` | `/api/me/alarms/{id}` | 必须 | 取消闹钟 |

### 活动（`activities` 模块）

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/api/activities` | 否 | 全部活动：进行中（open/running）在前且附成员列表（user_id/nickname/seq/status），归档（finished/cancelled）在后 |
| `GET` | `/api/me/activities` | 必须 | 当前用户参加过的全部活动（含 my_status/my_seq/my_submitted_at/进度） |
| `GET` | `/api/activities/{id}` | 否 | 活动详情（成员含 next_user_id/received_at、作品文字与图片 URL），不存在返回 404 |
| `GET` | `/archive/{id}/media/{filename}` | 否 | 活动作品图片（限制在 `ACTIVITY_ROOT` 内，防路径遍历） |

### 页面路由（FileResponse）

页面路由在各模块（前缀路径，根域 `/` 为 homepage 导航，不经 webapp）：

| 模块 | 路径 |
|--------|------|
| `gallery` | `/gallery` 图库主页 |
| `profile` | `/profile` 个人主页；`/profile/checkin` 网页打卡；`/profile/shop` 积分商店；`/profile/settings` 称号设置 |
| `trpg` | `/trpg` 车卡管理；`/trpg/char/{user_id}/{char_id}` 角色卡只读查看页 |
| `guestbook` | `/guestbook` 留言簿 |
| `alarms` | `/alarms` 闹钟管理 |
| `activities` | `/activities` 活动归档（三区块：我参加的活动（登录可见）/ 进行中的活动（含成员列表）/ 活动归档）；`/activities/{activity_id}` 活动详情页（标题/发起时间/报名结束/截止/状态/详情/参加人员；接龙 running 显示当前轮到谁与剩余时间；匹配 running 显示每人下家；归档展示作品），不存在返回 404 |

---

## Constraint: 跑团车卡

角色卡与个人设置**不存 SQLite**，改存 JSON 文件（bot 与各子应用共用 `core/character_store.py` / `core/user_settings.py`，写路径均为原子写 tmp + os.replace）：

```
server_data/trpg_chars/<user_id>/meta.json        # {"current_id": 3, "order": [1,2,3]}
server_data/trpg_chars/<user_id>/<char_id>.json   # 单个角色完整数据（任意嵌套 dict）
server_data/user_settings/<user_id>.json          # 个人设置（文件不存在 = 全默认值）
```

- 根目录可用 `BOTERO_TRPG_CHARS_ROOT` / `BOTERO_USER_SETTINGS_ROOT` 环境变量覆盖（默认见上文配置表）
- **隐私开关:** `privacy.char_public`（bool，缺省 `True`）。`GET /api/characters/{user_id}/{char_id}` 仅本人或对方已公开时可访问，否则返回 403
- 设置经 `GET/PUT /api/me/settings` 读写，`PUT` 深合并，不覆盖未传字段
- 角色创建/更新由 `core/trpg/character.py` 的 `finalize()` 计算派生值，非法数据返回 400
- `level` 不入盘编辑，由 `xp` 派生：`xp>0` 时按 `XP_THRESHOLDS`（`core/trpg/rules.py:72`，20 级阈值表，索引 0=1 级）反推，`xp<=0` 时回退原 `level` 字段
- **旧数据迁移**：提交（创建/更新）时若 `xp<=0 且 level>1`，自动回填 `xp = XP_THRESHOLDS[level-1]`（阈值下限）
- `race`/`class_name` 仅可选官方清单（`/api/trpg/rules` 的 `races`/`classes` 键，编辑器为 select）；旧数据自定义文本读侧兼容——编辑时追加「（自定义）」临时选项，服务端对未知种族/职业按无属性加值/HP 骰 8 处理（`race_bonuses()`/`class_info()` 返回空）
- 属性生成三方式（编辑器按钮，结果直接写入 `*_score`，服务端不区分来源）：**购点法**（属性值 8-15，总额 27 点，成本表 `POINT_BUY_COST`）、**4d6k3 掷骰**（掷 4 取 3）、**标准数组** `[15,14,13,12,10,8]`
- `/api/trpg/rules` 额外返回 `xp_thresholds`（经验阈值表）与 `alignments`（九宫格双轴：`{law:[守序,中立,混乱], moral:[善良,中立,邪恶]}`）

### 角色卡字段清单（5E 主卡面）

基础：`char_name` / `race` / `class_name` / `level` / `background` / 六维属性 `*_score` / `proficient_skills` / `hp` / `ac` / `notes`。5E 主卡面扩展：

| 分区 | 键（类型） |
|------|-----------|
| 身份 | `alignment` (str，九宫格组合：守序/中立/混乱 × 善良/中立/邪恶，中立×中立=`绝对中立`，存组合字符串如「守序善良」；非九宫格自定义文本仍可写入)、`xp` (int，等级派生源) |
| 属性豁免 | `saving_profs` (list[str]，6 属性名) |
| 战斗 | `current_hp` (int)、`temp_hp` (int)、`speed` (int，缺省 30)、`death_saves_success` (int)、`death_saves_fail` (int)、`inspiration` (bool) |
| 资源 | `equipment` (list[str]，每行一条)、`other_proficiencies` (str)、`attacks` (list[str]，格式 `名称|加值|伤害`，如 `长剑|+5|1d8 挥砍`)、`features` (str) |
| 背景四要素 | `personality_traits` / `ideals` / `bonds` / `flaws`（均 str） |

### 派生计算口径（不入盘，由 `finalize()` 计算）

以下字段**不写入角色卡 JSON**，每次读取时由 `core/trpg/character.py:finalize()` 计算：

- `scores` = 基础属性 + 种族加值（`str_score` 等六键覆盖写回）；`hp`/`ac` 例外：已有非零值则保留，否则按 `hp=职业骰+体质加值`、`ac=10+敏捷加值` 计算并**写回存储**
- `level` = `xp>0 ? level_from_xp(xp) : 原 level`（`level_from_xp` 按 `XP_THRESHOLDS` 反推，见 `core/trpg/character.py:13`）
- `prof_bonus` = `2 + (level-1)//4`
- `save_mods`（6 属性名→值）= 属性加值 +（该属性 ∈ `saving_profs` ? `prof_bonus` : 0）
- `skill_mods`（技能名→值）= 属性加值 +（技能 ∈ `proficient_skills` ? 2 : 0）
- `passive_perception` = `10 + 感知加值 + (察觉 ∈ proficient_skills ? 2 : 0)`
- `initiative` = 敏捷加值
- `hit_dice` = `{level}d{职业骰}`

---

## Constraint: 服务层模式

每个业务域的服务模块与路由分离，全部位于 `webapp/` 包内：

```
webapp/gallery/    repository.py    ← 数据库只读访问层（图库查询）
                   thumbnails.py    ← 缩略图生成/缓存
                   dates.py         ← 结算日计算
webapp/profile/    profile_service.py   ← 档案数据构建
                   checkin_service.py   ← 打卡业务逻辑
                   shop_service.py      ← 商店兑换
                   title_settings.py    ← 称号装备管理
webapp/alarms/     alarm_service.py     ← 闹钟 CRUD
webapp/guestbook/、webapp/trpg/、webapp/activities/   逻辑已在各自 app.py 或 core/db/ manager
```

---

## Constraint: 仓储层（`webapp/gallery/repository.py`）

独立于 Bot 端 `DbManager` 的只读数据库访问：

```python
# 上下文管理器模式
with _connect() as conn:
    conn.execute("SELECT ...", params)
    return conn.fetchall()

# row_factory = sqlite3.Row（返回字典式行）
```

**REMEMBER_MARKER:** 查询打卡数据时排除 `content = "remedy_checkin"` 的记录。`profile` 模块依赖本模块（`CheckinImage`、`fetch_user_settlement_day`）。

---

## Constraint: 安全

### 路径遍历防护

```python
# _assert_under_root(path) 验证文件在允许的目录内
# 用户提供的 user_id 和 filename 中禁止 ".." 和 "/"
```

### 上传限制

- 单次最多 `CHECKIN_MAX_IMAGES` 张（默认 9）
- 单张最大 `CHECKIN_MAX_BYTES` 字节（默认 10MB）

### 认证盐值

- `AUTH_SALT` 默认值为 `"BotEro-Gallery-ChangeMe"`（定义于 `core/config.py`，环境变量 `BOTERO_AUTH_SALT` 驱动）
- **部署单一来源**：`scripts/botero.env`（bot 的 `main.py` 启动时加载、webapp 经 systemd `EnvironmentFile` 注入），两进程共用同一盐值；改盐只改该文件

---

## Constraint: 静态前端

共享静态（`core/web/static/`，唯一挂载点 `/shared`，由 `webapp/app.py` mount）：

```
core/web/static/
  auth.js       ← 认证 token 管理（单 origin localStorage 共享；保留根域 cookie 写入兼容旧缓存）
  gallery.css   ← 图库样式
  profile.css   ← 个人中心样式
```

全部模块静态合并为**单一目录 `webapp/static/`**（文件名全局唯一，以 `/static` 挂载，由 `webapp/app.py` mount）：

```
webapp/static/
  index.html + gallery.js                       ← 图库主页（瀑布流 + 无限滚动）
  profile.html/js、checkin.html/js、shop.html/js、settings.html/js
  trpg.html/js（车卡管理）、char_view.html/js（只读查看）、trpg.css
  guestbook.html/js、guestbook.css
  alarms.html/js、alarms.css
  activities.html/js、activities_detail.html/js
```

导航主页位于 `webapp/homepage/`（`index.html` + `app.js` + `style.css` + `entries.json`/`notices.json`/`quotes.json`），由 `webapp/app.py` 在根路径 `/` 与 `/style.css` `/app.js` `/entries.json` `/notices.json` `/quotes.json` 提供；`entries.json` 为唯一入口维护点。登录态与全站统一（引入 `/shared/auth.js`，`GalleryAuth.renderAuth` 渲染登录按钮/用户卡片，样式走主页 style.css 的报纸风 token）。

- 原生 JavaScript，无框架
- 认证 token 通过 `Authorization: Bearer <token>` 传递
- 同源引用一律用根相对路径（如 profile 的媒体 URL 为 `/media/...`、分区间跳转 `/gallery` 等），不内链其他分区绝对路径

---

## Constraint: 部署

- 完整部署（systemd unit 示例、环境变量注入、Caddy 反代配置）见 [`docs/web-apps-deployment.md`](../docs/web-apps-deployment.md)
- 单进程 `python -m webapp`（默认 8765），`WorkingDirectory` 指向仓库根，环境注入 `BOTERO_DB_PATH` / `BOTERO_GALLERY_PORT` 等；`BOTERO_AUTH_SALT` 经 `scripts/botero.env`（EnvironmentFile）注入；systemd 单 unit `botero-web.service`，Caddy 根域 `littlero.tech` 全部流量反代 8765（主页/分区/API 均由 webapp 路由）；无子域 DNS

