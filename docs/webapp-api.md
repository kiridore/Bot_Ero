# BotEro Webapp API 参考

适用版本 **2.0.0+**。本文是面向客户端（web 前端、Flutter 移动/PC 端）的人类可读参考；**机器权威契约是 `GET /openapi.json`**（登录态可取，含全部参数与响应 schema，可配 openapi_generator 生成类型化客户端）。

- 生产 Base URL：`https://littlero.tech`（本地联调 `http://127.0.0.1:8765`）
- 全部 API 为 JSON over HTTP；未携带凭证访问非豁免端点 → `401 {"detail": "未登录"}`
- 获取 openapi 快照（提交进客户端仓库，契约变化在 PR diff 可见）：

```bash
curl -H "Authorization: Bearer <图库密钥>" https://littlero.tech/openapi.json > openapi.json
```

## 认证

凭证是**图库密钥**：用户向机器人 QQ 私聊发送 `/图库密钥` 领取（按 QQ 号签发的 HMAC 密钥）。

| 端点 | 说明 |
|---|---|
| `POST /api/auth/login` | body `{"key": "<图库密钥>"}` → `{user_id, display_name, avatar_url, token}`；**token 即图库密钥本身**，无过期 |
| `GET /api/auth/me` | 携带凭证 → 当前会话信息（同上，token 为空） |

- 其后所有请求带 `Authorization: Bearer <token>`（web 端也可用根域 cookie `botero_key`）。
- **豁免**（不需要用户凭证）：`POST /api/auth/login`、`/api/timeline/events*`（bot 上报，用独立事件令牌）。
- 密钥为确定性签名：重发 `/图库密钥` 得到同一把钥匙；**单用户不可吊销**，全局吊销手段 = 服务端轮换盐（全体重领）。客户端应允许用户随时替换密钥。

## 通用约定

- **错误体**：`{"detail": <string | 校验错误数组>}`（FastAPI 默认）。**HTTP 状态码属于契约；`detail` 文案不属于**——只展示、不解析、不做逻辑分支。
- **分页双形态**（全局无 `limit` 参数）：
  - 偏移列表：`?page=1&page_size=20` → `{"items": [...], "total": int, "page": int, "page_size": int, "has_more": bool?}`；`page_size` 上限逐端点在 openapi 声明；页码超界返回空 `items` 不报错；`page=0`/`page_size=0` → 422。
  - 游标信息流（时间线、论坛帖子/评论）：`?cursor=...&page_size=20` → `{"items": [...], "next_cursor": ...}`（时间线为 `events` 形态）；首页不传 cursor，续读传上次响应的 `next_cursor`，`next_cursor: null` 即取尽。
- **媒体**：载荷内的图片引用一律为相对路径或文件名，客户端以 Base URL 拼接；六个媒体前缀（`/thumb/`、`/media/`、`/forum/media/`、`/archive/`、`/trpg/media/`、`/donate/media/`）均要求凭证（Flutter 的 Image 组件传 headers）。
- **时间格式**：`YYYY-MM-DD HH:MM:SS`（部分展示场景截断到 `YYYY-MM-DD HH:MM`）。
- **契约演进**：默认只做 additive 变更（加字段/加端点）；破坏性变更会 minor bump 并在 CHANGELOG 显著标注，旧形态至少保留一个版本。

## 端点目录

认证列：必须 = 需 Bearer；可选 = 匿名可访问但登录后有个性化数据；机器 = 独立事件令牌。

### 认证与导航

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| POST | `/api/auth/login` | 无 | 密钥换取会话信息 |
| GET | `/api/auth/me` | 必须 | 当前用户昵称/头像 |
| GET | `/api/nav` | 必须 | 导航卡片数组 `[{name, desc, url?, badge?, span?, links?[{label, url?, copy?}]}]`（主页网格 + 侧边栏数据源） |

### 时间线（`timeline`）

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| GET | `/api/timeline` | 必须 | 信息流（游标式）：`?cursor&page_size` → `{events, users, next_cursor}`；服务端已解析昵称/头像与 `{id:QQ}` 占位符；打卡事件按作者隐私设置做 hidden/blur/text 处理（`data.images` 改写/清空，附 `images_hidden`；本人可见附 `self_only`），每条打卡事件另带与查看者无关的 `checkin_state`（`show|blur|text|hidden`，作者设置原值；非打卡事件无此键） |
| GET | `/api/timeline/poll` | 必须 | 轻量轮询：`?after=<seq>` → `{count}`（比 after 新且未读的可见事件数） |
| GET | `/api/timeline/new` | 必须 | 拉新：`?after&page_size` → `{events, users, next_after}`（最老一批在前转成新→旧；循环用 next_after） |
| POST | `/api/timeline/read` | 必须 | 逐卡已读回执 body `{event_ids: [...]}` → `{ok, remaining}` |
| POST | `/api/timeline/events` | 机器 | 事件上报（bot 专用；幂等，协议见 specs/timeline-protocol.md） |
| DELETE | `/api/timeline/events/{event_id}` / `.../by-key?source&key` | 机器 | 事件撤回 |

事件对象：`{seq, id, source, received_at, actor{id,qq,display_name,avatar_url}, target{type,url}?, title, description?, data?, unread}`。

### 打卡画廊（`gallery`）

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| GET | `/api/users` | 必须 | 有打卡记录的用户列表（含昵称） |
| GET | `/api/checkins` | 必须 | 打卡图片墙（偏移分页）；过滤 `user_id`/`year`/`only_with_file`；条目含 `thumbnail_url`/`image_url`（相对路径）与 `has_file`。按查看者应用作者打卡显示设置：作者本人全部可见（原图）；非作者 `show` 原图、`blur` 两支 URL 均为 `/thumb/…?blur=1`、`text`/`hidden` 条目不下发，`total` 只统计可见项 |
| GET | `/thumb/{user_id}/{filename}`、`/media/{user_id}/{filename}` | 必须 | 缩略图 / 原图（二进制） |

### 个人中心（`profile`）

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| GET | `/api/me/profile` | 必须 | 年度聚合：积分、连续打卡（`streaks{longest_daily,current_daily,longest_weekly,current_weekly}`）、热力图 `heatmap[{date,count,level,is_remedy}]`、称号列表（含解锁进度） |
| GET | `/api/me/day?date=` | 必须 | 某日结算记录 |
| GET | `/api/me/checkins` | 必须 | 本人打卡历史（偏移分页，`page_size` 固定 24） |
| GET | `/api/me/checkin/status` | 必须 | 本周打卡状态（张数/首图标记/连续/上限） |
| POST | `/api/me/checkin` | 必须 | 网页打卡（multipart `files`，与 QQ 打卡同账本同结算）→ 含加成明细、解锁称号、汇总文案 |
| GET | `/api/me/avatar.png` | 必须 | 头像 PNG（二进制） |
| GET | `/api/me/shop` | 必须 | 积分商店货架（含库存/已拥有/可购标记） |
| POST | `/api/me/shop/redeem` | 必须 | 兑换商品 body `{product_id}` |
| GET | `/api/me/redeem/history` | 必须 | 兑换码历史 |
| POST | `/api/me/redeem` | 必须 | 使用兑换码 body `{code}`（大小写不敏感） |
| GET | `/api/me/titles/settings` | 必须 | 称号佩戴设置（equipped/unlocked/display_prefix） |
| PUT | `/api/me/titles/equipped` | 必须 | 整体设置佩戴 body `{title_ids}`（上限见 max_equipped） |
| POST | `/api/me/titles/equip`、DELETE `/api/me/titles/equip/{title_id}`、DELETE `/api/me/titles/equipped` | 必须 | 佩戴/卸下/清空 |
| GET/PUT | `/api/me/settings` | 必须 | 个人设置（privacy、email 绑定态） |
| POST | `/api/me/email/code` / `bind` / `unbind` | 必须 | 邮箱验证码流程（purpose=bind/unbind；服务未配置 503） |

### 议事厅（`forum`）

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| GET | `/api/forum/posts` | 必须 | 帖子列表（游标式）；过滤 `tag`/`type=post|announce|poll` |
| POST | `/api/forum/posts` | 必须 | 发帖（长文/公告/投票帖；公告每人每日 1 条 429；正文为 Tiptap JSON 字符串） |
| GET | `/api/forum/posts/{id}` | 必须 | 帖子详情（投票帖附 `polls[].options[].count` 与本人 `my_vote`；每次 GET 浏览数 +1） |
| PATCH | `/api/forum/posts/{id}` | 必须 | 编辑自己的帖子（tags：null=不动 []=清空） |
| DELETE | `/api/forum/posts/{id}` | 必须 | 删自己的帖子 |
| GET | `/api/forum/posts/{id}/comments` | 必须 | 评论两级线程（游标式，含 total；回复条目附 reply_to_*） |
| POST | `/api/forum/posts/{id}/comments` | 必须 | 评论/回复 body `{body_text, parent_id?}` |
| PATCH | `/api/forum/comments/{id}`、DELETE 同路径 | 必须 | 编辑/删除自己的评论 |
| POST | `/api/forum/posts/{id}/vote` | 必须 | 投票 body `{poll_id, option_ids}`（重复 409、截止 422） |
| POST | `/api/forum/posts/{id}/close` | 必须 | 作者提前关闭投票 |
| GET | `/api/forum/tags`、POST 同路径 | 必须/必须 | tag 云（含帖子数）/ 新建 tag |
| POST | `/api/forum/images` | 必须 | 正文图片上传（multipart）→ `{url: "/forum/media/<uuid>"}` |
| GET | `/forum/media/{filename}` | 必须 | 帖子图片（二进制） |

### 留言簿（`guestbook`）

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| GET | `/api/guestbook` | 可选 | 留言列表（偏移分页，按赞数排；登录后附 `liked`） |
| POST | `/api/guestbook` | 必须 | 留言 body `{content}` |
| POST | `/api/guestbook/{entry_id}/like` | 必须 | 点赞（不能赞自己） |

### 工具箱（`tools`）

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| GET | `/api/tools` | 可选 | 全量链接卡片（无分页）；每项含 `tags`（tag 名数组）；过滤 `q`/`tag`，排序 `sort=time|hot`、`order=asc|desc` |
| GET | `/api/tools/icon?domain=` | 可选 | 站点图标（二进制；无图标 404，负缓存 7 天） |
| GET | `/api/tools/tags` | 可选 | tag 及计数 |
| POST | `/api/tools` | 必须 | 提交链接 body `{title, description, url, tags}` |
| POST | `/api/tools/{id}/click` | 可选 | 点击计数 → `{clicks}` |
| PUT | `/api/tools/{id}`、DELETE 同路径 | 必须 | 修改/删除自己提交的链接 |

### 活动（`activities`）

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| GET | `/api/activities` | 必须 | 全部活动（进行中在前，附成员概要；归档项只有计数） |
| POST | `/api/activities` | 必须 | 创建（relay 接龙 / match 匹配 / collect 征集；match/collect 必带截止；每群唯一进行中）→ 含 `announce` 群公告文案 |
| GET | `/api/activities/{id}` | 必须 | 详情（成员链序、`eta_deadline` 接龙预计截止；**进行中他人 content/images 剥离**，归档后公开） |
| PATCH | `/api/activities/{id}` | 必须 | 创建人/超管编辑（状态限可编辑字段） |
| GET | `/api/activities/{id}/announce` | 必须 | 群公告文案（创建人/超管） |
| POST | `/api/activities/{id}/join` | 必须 | 报名（open 期；重复 409） |
| POST | `/api/activities/{id}/start` | 必须 | 请求开始（写报名截止=now，bot 心跳 ≤60s 内生效并通知） |
| POST | `/api/activities/{id}/finish` | 必须 | 请求提前结束（同上，未交者记 missed） |
| POST | `/api/activities/{id}/cancel` | 必须 | 取消（仅 open） |
| GET | `/api/activities/{id}/me` | 必须 | 我的参团状态与可提交判定（`can_submit`/`block_reason`/`block_text`） |
| POST | `/api/activities/{id}/submit` | 必须 | 增量提交作品（multipart：`content` 覆盖文本、`files` 追加、`removed` 删图） |
| GET | `/api/me/activities` | 必须 | 我参加过的活动 |
| GET | `/archive/{id}/media/{filename}` | 必须 | 活动作品（二进制） |

### 日程（`alarms`）

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| GET | `/api/me/alarms` | 必须 | 本人闹钟列表（私聊 + 本群群闹钟） |
| POST | `/api/me/alarms` | 必须 | 创建 body `{content, schedule_type(once_date|once_relative|once_today|daily|interval_days|weekly|monthly|yearly), date?, time?, 年/月/日/时/分?, interval_days?, weekday?, month?, day?, scope(private|group)}` |
| PUT | `/api/me/alarms/{id}` | 必须 | 修改（同 body） |
| DELETE | `/api/me/alarms/{id}` | 必须 | 取消 |
| GET | `/api/me/calendar?month=YYYY-MM` | 必须 | 按月展开 `days{日期: [{time, content, is_mine, scope, is_recurring, recur_desc, creator_name}]}`（服务端权威展开） |

### 跑团（`trpg`）

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| GET | `/api/me/characters` | 必须 | 我的角色卡列表 + current_id |
| POST | `/api/me/characters` | 必须 | 建卡（COC/DND 整卡数据，rules=dnd5e|coc7th） |
| GET/PUT/DELETE | `/api/me/characters/{id}` | 必须 | 查看/整卡保存/删除 |
| POST/DELETE | `/api/me/characters/{id}/age-adjust` | 必须 | COC 年龄调整（写前校验并同步派生值） |
| POST | `/api/me/characters/{id}/levelup` | 必须 | DND 升级向导结算 |
| POST | `/api/me/characters/{id}/activate` | 必须 | 设为当前卡 |
| GET | `/api/characters/{user_id}/{char_id}` | 必须 | 他人角色卡（对方未公开 403） |
| GET | `/api/trpg/coc/options` | 必须 | 建卡数据源：技能基础值/职业模板/武器库/币种/资产项/年龄段等 |
| GET | `/api/trpg/coc/skill-notes` | 必须 | 技能说明索引 |
| GET | `/api/trpg/coc/asset-reference?currency&credit&level` | 必须 | 资产参考值 |
| GET | `/api/trpg/rules` | 必须 | DND 5E 规则数据（属性/技能/购点表/升级阈值等） |
| GET | `/api/trpg/records?mine=` | 必须 | 跑团记录列表（附 is_mine/my_role） |
| GET | `/api/trpg/records/{group_id}/{start_dir}?from=&reveal=` | 必须 | 记录回放（增量 `from` 索引不漂移；`reveal` 揭示暗骰需 DM/超管语义由前端控制传参） |
| GET | `/api/trpg/parties` | 必须 | 准备中的团（名单/DM/角色卡入口，附 is_dm/can_audit） |
| GET | `/api/trpg/party/{group_id}/card/{user_id}` | 必须 | 准备名单角色卡（本人/本群 DM 可看，他人按隐私设置） |
| DELETE | `/api/trpg/party/{group_id}` | 必须 | 清除残留准备数据（DM/超管） |
| GET | `/trpg/media/{group_id}/{start_dir}/{filename}` | 必须 | 记录图片（二进制） |

### 直播（`live`）

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| GET | `/api/live/streams` | 必须 | `{"flv": url, "hls": url|null}`（桌面可播 FLV；移动端建议 HLS，null 时回落/隐藏） |
| GET | `/api/live/status` | 否 | 在线状态（服务端探测流） |
| POST | `/api/live/heartbeat` | 可选 | 观众在场心跳 body `{client_id}`（≥10s 间隔，75s 过期） |
| GET | `/api/live/viewers` | 否 | 当前观众列表 |

### 周报与赞赏

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| GET | `/api/weekly` | 必须 | 周报期目列表 |
| GET | `/api/weekly/{week_key}` | 必须 | 周报正文（数据结构随内容演进，客户端宽松解析） |
| GET | `/api/donate/images` | 必须 | 赞赏码图片名列表 |
| GET | `/donate/media/{filename}` | 必须 | 赞赏码图片（二进制） |

### App 更新（`appversion`）

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| GET | `/api/app/version` | 必须 | App 内更新清单：`{version, version_code, apk_url, sha256, size, notes, min_supported_version_code, published_at}`。`version_code` 为单调递增整数（客户端据此比较）；`version_code < min_supported_version_code` 时客户端强制更新；`sha256` 为 64 位小写 hex。APK 托管在外部对象存储，`apk_url` 是外部直链，本服务不托管、不代理二进制。**未配置**（`config.yaml` 无 `app_update` 段或 `apk_url` 为空）返回 **404**，客户端静默跳过；配置非法返回 500 且 `detail` 指明字段。发布流程见 `docs/app-release.md` |

## 客户端接入清单（Flutter）

1. 登录页：用户粘贴图库密钥 → `POST /api/auth/login` → 持久化 token（secure storage）。
2. openapi_generator + dio 按 openapi.json 快照生成客户端；全局给 dio 加 Bearer 拦截器（豁免路径除外）。
3. 媒体加载统一走「Base URL + 相对路径 + Authorization 头」。
4. 错误处理只看状态码；`detail` 原样展示。
