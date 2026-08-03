# Spec: 打卡图库 Web 应用

> 关联规范: [database.md](database.md) | [conventions.md](conventions.md) | [architecture.md](architecture.md)
> 父文档: [CLAUDE.md](../CLAUDE.md)
> 最后更新: 2026-08-03 (新增活动归档页 /archive 与接口)

---

## Constraint: 独立进程架构

Web 应用（`checkin_gallery/`）是独立的 FastAPI 进程，与机器人主进程分开运行。

```
┌─────────────────────┐     ┌─────────────────────────┐
│  main.py (bot)       │     │  checkin_gallery (web)   │
│  ws://127.0.0.1:3001 │     │  http://127.0.0.1:8765   │
└────────┬────────────┘     └───────────┬───────────────┘
         │                              │
         └──────────┬───────────────────┘
                    │
              ┌─────▼─────┐
              │  data.db   │  (共享 SQLite，web 端对打卡数据只读)
              └───────────┘
```

**启动:** `python -m checkin_gallery [--port PORT] [--db PATH] [--images PATH]`

---

## Constraint: 配置

所有配置通过环境变量（`checkin_gallery/config.py`）：

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `BOTERO_DB_PATH` | `data.db` | 数据库路径 |
| `BOTERO_IMAGE_ROOT` | `server_data/record_images` | 打卡图片目录 |
| `BOTERO_GALLERY_HOST` | `0.0.0.0` | 绑定地址（局域网可访问；仅本机用 `127.0.0.1`） |
| `BOTERO_GALLERY_PORT` | `8765` | 监听端口 |
| `BOTERO_ONEBOT_HTTP` | `http://192.168.0.103:3000` | OneBot HTTP API |
| `BOTERO_ONEBOT_TOKEN` | `123456` | OneBot HTTP 令牌 |
| `BOTERO_GROUP_ID` | `296470819` | 默认群号（昵称查询） |
| `BOTERO_THUMB_CACHE` | `server_data/thumb_cache` | 缩略图缓存目录 |
| `BOTERO_THUMB_MAX_WIDTH` | `480` | 缩略图最大宽度 |
| `BOTERO_THUMB_MAX_HEIGHT` | `720` | 缩略图最大高度 |
| `BOTERO_THUMB_QUALITY` | `82` | JPEG 缩略图质量 |
| `BOTERO_AUTH_SALT` | `BotEro-Gallery-ChangeMe` | HMAC 盐值（生产环境必须改） |
| `BOTERO_CHECKIN_MAX_IMAGES` | `9` | 单次打卡最大图片数 |
| `BOTERO_CHECKIN_MAX_BYTES` | `10485760` (10MB) | 单张图片最大字节 |
| `BOTERO_TRPG_CHARS_ROOT` | `server_data/trpg_chars` | 跑团角色卡 JSON 存储根目录 |
| `BOTERO_USER_SETTINGS_ROOT` | `server_data/user_settings` | 个人设置 JSON 存储根目录 |
| `BOTERO_ACTIVITY_ROOT` | `server_data/activity_archive` | 活动归档根目录（`<活动id>/` 子目录） |

---

## Constraint: HMAC 认证

```python
# 登录密钥生成（在 QQ 插件中）:
key = base64(
    base64(HMAC-SHA256(user_id, salt)[:12]).decode()
    + ":" + str(user_id)
)

# 验证（在 Web 端 checkin_gallery/auth.py）:
user_id = verify_login_key(key)  # 返回 user_id 字符串或 None
```

**依赖注入:**
- `Depends(get_current_user_id)` — 必须登录
- `Depends(get_optional_user_id)` — 可选登录（公开+登录混合路由）

---

## Constraint: API 路由

### 认证

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `POST` | `/api/auth/login` | 否 | 登录，返回 token |
| `GET` | `/api/auth/me` | 必须 | 当前用户信息 |

### 打卡数据

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/api/checkins` | 可选 | 分页打卡图片列表 |
| `GET` | `/api/me/day` | 必须 | 某结算日的打卡详情 |
| `GET` | `/api/me/profile` | 必须 | 用户档案（热度图、称号） |
| `GET` | `/api/me/checkin/status` | 必须 | 本周打卡状态 |
| `POST` | `/api/me/checkin` | 必须 | 网页端打卡上传（multipart） |
| `GET` | `/api/users` | 可选 | 所有有打卡记录的用户列表 |

### 商店

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/api/me/shop` | 必须 | 商店货架 |
| `POST` | `/api/me/shop/redeem` | 必须 | 兑换商品 |

### 闹钟

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/api/me/alarms` | 必须 | 闹钟列表 |
| `POST` | `/api/me/alarms` | 必须 | 创建闹钟 |
| `DELETE` | `/api/me/alarms/{id}` | 必须 | 取消闹钟 |

### 称号

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/api/me/titles/settings` | 必须 | 称号设置 |
| `PUT` | `/api/me/titles/equipped` | 必须 | 批量设置装备 |
| `POST` | `/api/me/titles/equip` | 必须 | 装备单个称号 |
| `DELETE` | `/api/me/titles/equipped` | 必须 | 卸下全部 |
| `DELETE` | `/api/me/titles/equip/{id}` | 必须 | 卸下单个 |

### 留言簿

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/api/guestbook` | 可选 | 留言列表 |
| `POST` | `/api/guestbook` | 必须 | 发表留言 |
| `POST` | `/api/guestbook/{id}/like` | 必须 | 点赞 |

### 跑团车卡

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
| `GET` | `/api/me/settings` | 必须 | 我的个人设置 |
| `PUT` | `/api/me/settings` | 必须 | 更新个人设置（深合并） |

### 媒体

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/thumb/{user_id}/{filename}` | 否 | 缩略图 |
| `GET` | `/media/{user_id}/{filename}` | 否 | 原图 |

### 活动归档

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/api/activities` | 否 | 已结束活动列表（含成员数/提交数） |
| `GET` | `/api/activities/{id}` | 否 | 活动详情（成员、作品文字与图片 URL），不存在返回 404 |
| `GET` | `/archive/{id}/media/{filename}` | 否 | 活动作品图片（限制在 `ACTIVITY_ROOT` 内，防路径遍历） |

### 页面

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 图库主页 |
| `GET` | `/profile` | 个人档案 |
| `GET` | `/profile/settings` | 称号设置 |
| `GET` | `/profile/checkin` | 网页打卡 |
| `GET` | `/profile/shop` | 积分商店 |
| `GET` | `/profile/alarms` | 闹钟管理 |
| `GET` | `/profile/trpg` | 跑团车卡管理（创建/编辑，Excel 式分区编辑器） |
| `GET` | `/trpg/char/{user_id}/{char_id}` | 角色卡只读查看页 |
| `GET` | `/guestbook` | 留言簿 |
| `GET` | `/archive` | 活动归档页 |

---

## Constraint: 跑团车卡

角色卡与个人设置**不再存 SQLite**，改存 JSON 文件（bot 与 web 双进程共用 `core/character_store.py` / `core/user_settings.py`，写路径均为原子写 tmp + os.replace）：

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

每个业务域一个服务模块，与路由处理分离：

```
app.py            ← FastAPI 路由（只做请求/响应转换）
  ├── checkin_service.py    ← 打卡业务逻辑
  ├── profile_service.py    ← 档案数据构建
  ├── shop_service.py       ← 商店兑换
  ├── alarm_service.py      ← 闹钟 CRUD
  ├── guestbook_service.py  ← 留言簿逻辑
  ├── title_settings.py     ← 称号装备管理
  ├── activity_service.py   ← 活动归档读取（bot 写盘，web 只读）
  └── repository.py         ← 数据库访问层
```

---

## Constraint: 仓储层 (`repository.py`)

独立于 Bot 端 `DbManager` 的数据库访问：

```python
# 上下文管理器模式
with _connect() as conn:
    conn.execute("SELECT ...", params)
    return conn.fetchall()

# row_factory = sqlite3.Row（返回字典式行）
```

**REMEMBER_MARKER:** 查询打卡数据时排除 `content = "remedy_checkin"` 的记录。

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

- `AUTH_SALT` 默认值为 `"BotEro-Gallery-ChangeMe"`
- 生产环境必须通过环境变量 `BOTERO_AUTH_SALT` 覆盖

---

## Constraint: 静态前端

```
checkin_gallery/static/
  index.html + gallery.js + gallery.css  ← 图库主页（瀑布流 + 无限滚动）
  auth.js                                 ← 认证 token 管理
  profile.html + profile.js + profile.css ← 个人档案页
  settings.html + settings.js             ← 称号设置页
  checkin.html + checkin.js               ← 网页打卡页
  shop.html + shop.js                     ← 商店页
  alarms.html + alarms.js               ← 闹钟管理页
  guestbook.html + guestbook.js         ← 留言簿页
  trpg.html + trpg.js                   ← 跑团车卡管理页
  char_view.html + char_view.js         ← 角色卡只读查看页
  activities.html + activities.js       ← 活动归档页
```

- 原生 JavaScript，无框架
- 通过 `StaticFiles` 挂载
- 认证 token 通过 `Authorization: Bearer <token>` 传递
