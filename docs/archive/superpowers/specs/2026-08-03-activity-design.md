# 群活动系统（接龙 / 匹配下家）设计

> 日期: 2026-08-03
> 状态: 已确认（设计评审通过）

## 背景

为群聊提供两类创作活动：

- **接龙（relay）**：一条作品链，A 开始创作 → 交给机器人 → 机器人转发给 B 继续 → … → 最后一人完成即结束。每人有独立的滚动计时器（从收到作品起算），超时跳过并顺延。
- **匹配下家（match）**：圆桌模型——所有人围坐一圈，每人创作一份作品交给自己的"下家"，作品单向传递（A→B→C→…→A 的闭合环）。下家身份**保密**（秘密圣诞老人式：只知道自己为谁创作，不知道谁为自己创作），机器人匿名转发。整个活动共享一个全局截止时间。

活动结束后归档内容（作品、作者、顺序），并在 `checkin_gallery` Web 应用新增归档展示页。

## 需求确认

| 项 | 结论 |
|----|------|
| 归档展示作者名 | 公开（纪念用途） |
| 接龙第一棒限时 | 限（从开始通知起算 `hours_per_user`） |
| 开始后允许退出 | 允许，见"退出处理" |
| 匹配玩法 | 单环（shuffle 错位），单向，A 创作给 B、B 创作给 C，互不知晓上家 |
| 作品提交 | 私聊一条消息（文字/图片/文字+图片），一次一条，不支持修改 |
| 官网归档 | `checkin_gallery` 新增活动页 |
| 匹配中途退出、作品已发出 | 不追回（留在收件人处） |

## 核心架构决策

**DB 全持久化**（`data.db` 两张新表）。活动跨数天、`/更新` 重启进程，内存态（`who_is_spy` 风格）会丢活动；提交即落库，重启后"当前轮到谁"可从表推导，计时用绝对时间不受重启影响。

匹配环生成：**shuffle 后错位成单环**（`next[i] = shuffled[(i+1) % n]`），人人有下家、无自匹配，构成"圆桌"语义。

## 数据层（`data.db` 新增 2 表）

### `activities`

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | 活动号（展示用） |
| group_id | INTEGER | 所属群 |
| type | TEXT | `relay` / `match` |
| title | TEXT | 标题 |
| theme | TEXT | 可选主题（可空） |
| status | TEXT | `open`（报名）→ `running`（进行中）→ `finished`（已归档）/ `cancelled` |
| created_by | TEXT | 创建人 QQ |
| deadline | TEXT | 仅 match：全局截止 `YYYY-MM-DD HH:MM` |
| hours_per_user | REAL | 仅 relay：每人完成时限（小时） |
| created_at | TEXT | |
| finished_at | TEXT | 可空 |

### `activity_members`

| 列 | 类型 | 说明 |
|----|------|------|
| activity_id | INTEGER | 联合主键 |
| user_id | TEXT | 联合主键，QQ |
| nickname | TEXT | 加入时昵称 |
| seq | INTEGER | relay：链顺序 1..N；match：shuffle 索引 |
| next_user_id | TEXT | match：下家 QQ（为其创作的人）；relay 由 seq 推导 |
| status | TEXT | `pending` / `done` / `skipped`（接龙超时跳过）/ `missed`（匹配截止未交）/ `left`（退出） |
| received_at | TEXT | relay：作品转交给 TA 的时刻（计时起点）；第一棒为开始通知时刻 |
| submitted_at | TEXT | 可空 |
| content | TEXT | 文字作品，可空 |
| images | TEXT | JSON 数组（图片文件名），可空 |

`database_manager.py` 按现有 `?` 参数化风格新增表结构与访问方法。

## 指令系统

**群聊**（每群同一时间只允许一个非 `finished`/`cancelled` 的活动）：

| 指令 | 权限 | 说明 |
|------|------|------|
| `/活动 创建 接龙 <标题> [每人小时数]` | 任意（该群无活动时） | 默认 48 小时 |
| `/活动 创建 匹配 <标题> <截止 YYYY-MM-DD HH:MM>` | 任意 | |
| `/活动 加入` | 任意 | 报名期 |
| `/活动 退出` | 任意 | 报名期直接移除；进行中走"退出处理" |
| `/活动 开始` | 仅创建人 | 报名截止，生成顺序/匹配，私聊逐一通知 |
| `/活动 状态` | 任意 | 进度：谁完成/轮到谁/剩余时间 |
| `/活动 结束` | 仅创建人 | 提前结束并归档 |

**私聊**：

| 指令 | 说明 |
|------|------|
| `/提交 [活动id]` | 同一条消息内带文字或图片即提交。只参与一个活动时无需 id；多个活动需指定（防串台） |

## 作品流转

**接龙**：A 提交 → 机器人原样转发给下一位 B（附"请接力，N 小时内完成"）→ B 的 `received_at` 起算 → … → 链走完 → 结束归档。
**匹配**：A 提交 → 机器人**匿名**转发给下家 B（不附作者名）→ 全员提交或截止到点 → 结束归档。

## 计时与超时（心跳）

新增 `ActivityTimerPlugin`（meta 心跳事件，60 秒节流，类级 dict 记录上次扫描时刻，复用 `TimedHeartbeatPlugin._last_run_minute` 模式，不依赖 `RUN_AT`）：

- relay：扫描当前轮到的人，`now - received_at > hours_per_user` → 标 `skipped`，作品转给下一人 + 群公告 @该人
- match：扫描 `deadline` 到点 → 未提交者标 `missed` → 结束归档

## 退出处理（进行中）

| 类型 | 处理 |
|------|------|
| 接龙 | 从链中摘除（标 `left`），作品直接传给下一位（等同跳过）；已提交作品保留在归档 |
| 匹配 | 从环中摘除（标 `left`）：**前驱的下家原地更新为后继**，环重新闭合，无需洗牌、无需通知全员；未提交的前驱私聊通知"你的下家已变更"。已送达的作品不追回 |

例子：环 `Y → X → D`，X 退出后变 `Y → D`，Y 未提交则改发给 D。D 匿名收件无感。

## 结束与归档

活动结束（relay 链走完 / match 截止或全员提交 / 手动结束）触发归档：

```
server_data/activity_archive/<activity_id>/
├── meta.json          # 活动信息、参与者（昵称+QQ+状态）、类型、时间
├── relay.md           # 接龙：按链序分段，每段 作者/提交时间/文字 + 图片引用
├── match.md           # 匹配：按作品分段（作者名公开），文字 + 图片引用
└── imgs/              # 图片（get_image_url + download_image 下载，同 trpg_session 模式）
```

图片命名 `img_<seq>_<n>.jpg` 避免冲突（seq 为链序/环序）。DB 置 `finished` + `finished_at`。

## Web 端（checkin_gallery）

- `config.py` 新增 `ACTIVITY_ROOT`（默认 `server_data/activity_archive`，环境变量 `BOTERO_ACTIVITY_ROOT`）
- 新增 API：`GET /api/activities`（已归档列表）、`GET /api/activities/{id}`（详情：分段文字 + 图片 URL）
- 新增页面 `static/activities.html` + `activities.js`（复用 HMAC 登录鉴权与现有页面样式）
- 图片静态服务复用现有图库机制（图片文件 + URL 映射）

## 边界处理

- 不是当前轮到的人提交 / 重复提交 / 未参加提交 → 明确提示
- 提交图片下载失败 → 告知失败可重试
- 零提交 / 全员 skipped → 仍归档（meta 标注）
- 私聊 `/提交` 无法判定唯一活动 → 提示指定活动 id
- 群内报名期无人 → 创建人可 `/活动 结束` 取消（`cancelled`）

## 同步维护（同 commit）

- `specs/plugin-catalog.md`（新增 2 插件条目）
- `specs/database.md`（新表）
- `plugins/bot_menu_text.py`（新指令）
- `specs/web-gallery.md`（新 API/页面）
- `KNOWLEDGE_BASE.md` / `kb/QUICK_REFERENCE.md`

## 测试

`test/` 下纯函数自检脚本（无框架）：

- 匹配环生成：无自匹配、单环闭合、参与者齐全
- 接龙超时判定：时间注入
- 退出摘除逻辑：环闭合正确
- 状态机流转：open → running → finished
