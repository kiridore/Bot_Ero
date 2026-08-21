# 数据库 Schema

> `data.db` 全部 44 张表（`core/db/_base.py::init_schema`）+ 独立库 `message_log.db` 1 张，结构与约束
>
> 参见 `specs/database.md` 获取更简化的概述

---

## 用户与积分

```sql
-- 注意: user_id 在旧表中为 TEXT，新表统一用 INTEGER
CREATE TABLE user_assets (
    user_id TEXT PRIMARY KEY,
    points INTEGER DEFAULT 0
);
```

## 打卡

```sql
CREATE TABLE checkin_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    checkin_date TEXT NOT NULL,     -- YYYY-MM-DD HH:MM:SS
    content TEXT NOT NULL,          -- 图片文件名 或 "remedy_checkin"
    message_id INTEGER              -- QQ 消息 ID（ALTER 后加的列）
);
```

```sql
CREATE TABLE user_remedy_usage (
    year INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    used_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (year, user_id)
);
```

## 积分/奖励领取

```sql
CREATE TABLE user_weekly_streak_reward_claims (
    user_id INTEGER NOT NULL,
    week_start TEXT NOT NULL,
    claimed_at TEXT NOT NULL,
    PRIMARY KEY (user_id, week_start)
);

CREATE TABLE user_attendance_reward_claims (
    user_id INTEGER NOT NULL,
    reward_type TEXT NOT NULL,       -- full_week_daily, full_month_weekly_check
    period_key TEXT NOT NULL,
    points INTEGER NOT NULL,
    claimed_at TEXT NOT NULL,
    PRIMARY KEY (user_id, reward_type, period_key)
);

CREATE TABLE redeem_code_usage (
    user_id INTEGER NOT NULL,
    code TEXT NOT NULL,              -- 兑换码（大写规范化，如 TEST-CODE-TEST）
    used_at TEXT NOT NULL,
    PRIMARY KEY (user_id, code)      -- 每用户每码一次
);
```

## 周常任务

```sql
CREATE TABLE quest_progress (
    user_id TEXT NOT NULL,
    quest_id INTEGER NOT NULL,
    week_key TEXT NOT NULL,          -- 周一日期 YYYY-MM-DD
    progress INTEGER DEFAULT 0,
    completed INTEGER DEFAULT 0,
    claimed_at TEXT,
    PRIMARY KEY (user_id, quest_id, week_key)
);

CREATE TABLE quest_completion_stats (
    user_id TEXT PRIMARY KEY,
    total_completions INTEGER DEFAULT 0
);

CREATE TABLE quest_weekly_clears (
    user_id TEXT NOT NULL,
    week_key TEXT NOT NULL,
    cleared_at TEXT NOT NULL,
    PRIMARY KEY (user_id, week_key)
);
```

## 称号

```sql
CREATE TABLE user_titles (
    user_id TEXT NOT NULL,
    title_id INTEGER NOT NULL,
    unlocked_at TEXT NOT NULL,
    PRIMARY KEY (user_id, title_id)
);

CREATE TABLE user_equipped_titles (
    user_id TEXT NOT NULL,
    slot INTEGER NOT NULL,           -- 1-3
    title_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, slot),
    UNIQUE (user_id, title_id)
);

-- Legacy: 旧版单称号，已迁移
CREATE TABLE user_title_state (
    user_id TEXT PRIMARY KEY,
    equipped_title INTEGER
);
```

## 抽奖

```sql
CREATE TABLE user_lottery_daily_stats (
    stat_date TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    draw_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (stat_date, user_id)
);

CREATE TABLE user_lottery_stats (
    user_id INTEGER PRIMARY KEY,
    total_spent INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE user_lottery_profile (
    user_id INTEGER PRIMARY KEY,
    draw_count INTEGER NOT NULL DEFAULT 0,
    duplicate_count INTEGER NOT NULL DEFAULT 0,
    zero_streak INTEGER NOT NULL DEFAULT 0,
    max_zero_streak INTEGER NOT NULL DEFAULT 0,
    has_hit_ten INTEGER NOT NULL DEFAULT 0,
    total_zeros INTEGER NOT NULL DEFAULT 0
);
```

## 商店

```sql
CREATE TABLE shop_stock (
    product_id TEXT PRIMARY KEY,
    stock INTEGER NOT NULL           -- -1 = 无限
);

CREATE TABLE shop_user_buffs (
    user_id INTEGER PRIMARY KEY,
    extra_draw_pack_until TEXT,
    checkin_luck_remaining INTEGER NOT NULL DEFAULT 0,
    lottery_waiver_remaining INTEGER NOT NULL DEFAULT 0
);
```

## 闹钟

```sql
CREATE TABLE group_alarms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,       -- 私聊=0
    creator_user_id INTEGER NOT NULL,
    fire_at TEXT NOT NULL,           -- YYYY-MM-DD HH:MM:SS
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    fired INTEGER NOT NULL DEFAULT 0,
    is_private INTEGER NOT NULL DEFAULT 0,
    is_recurring INTEGER NOT NULL DEFAULT 0,
    repeat_y INTEGER NOT NULL DEFAULT 0,             -- Legacy
    repeat_m INTEGER NOT NULL DEFAULT 0,             -- Legacy
    repeat_d INTEGER NOT NULL DEFAULT 0,             -- Legacy
    recur_kind INTEGER NOT NULL DEFAULT 0,           -- 0=单次,1=每N日,2=每周,3=每月,4=每年
    recur_a INTEGER NOT NULL DEFAULT 0,
    recur_b INTEGER NOT NULL DEFAULT 0,
    recur_c INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_group_alarms_due ON group_alarms (fired, fire_at);
```

## 仙人彩

```sql
CREATE TABLE immortal_lottery_carry (
    group_id INTEGER NOT NULL PRIMARY KEY,
    carry_4a INTEGER NOT NULL DEFAULT 0,
    carry_3a INTEGER NOT NULL DEFAULT 0,
    carry_2a INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE immortal_lottery_results (
    group_id INTEGER NOT NULL,
    period_key TEXT NOT NULL,
    winning_digits TEXT NOT NULL,
    bet_total INTEGER NOT NULL DEFAULT 0,
    drawn_at TEXT NOT NULL,
    PRIMARY KEY (group_id, period_key)
);

CREATE TABLE immortal_lottery_bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    period_key TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    digits TEXT NOT NULL,
    bet_bj_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (group_id, user_id, bet_bj_date)
);
CREATE INDEX idx_immortal_bets_period ON immortal_lottery_bets (group_id, period_key);

CREATE TABLE immortal_lottery_issue (
    group_id INTEGER NOT NULL,
    period_key TEXT NOT NULL,
    issue_code TEXT NOT NULL,
    PRIMARY KEY (group_id, period_key),
    UNIQUE (issue_code)
);
```

## 留言簿

```sql
CREATE TABLE guestbook_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_guestbook_entries_created ON guestbook_entries (created_at DESC);

CREATE TABLE guestbook_likes (
    entry_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (entry_id, user_id),
    FOREIGN KEY (entry_id) REFERENCES guestbook_entries(id)
);
```

## 群插件配置

```sql
CREATE TABLE group_plugin_config (
    group_id INTEGER NOT NULL,       -- 0 = 私聊/全局配置
    plugin_name TEXT NOT NULL,       -- plugin_key(cls) 如 "checkin"
    PRIMARY KEY (group_id, plugin_name)
    -- 有行 = 启用，无行 = 禁用
);
```

### 默认策略

- 新群/新增插件默认全部禁用
- 首次部署时自动为 `DEFAULT_GROUP_ID` 启用所有非系统插件

### 检查层级

- `meta` 事件 → 跳过检查，所有插件运行
- 系统插件 (`SYSTEM_PLUGINS`) → 始终运行，不可禁用
- 群消息 → 查 `group_id = 当前群`
- 私聊消息 → 查 `group_id = 0`

---

## 活动

```sql
CREATE TABLE activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    type TEXT NOT NULL,                -- 'relay' | 'match'
    title TEXT NOT NULL,
    description TEXT,                -- 活动描述（可选；旧列名 theme 已迁移）
    status TEXT NOT NULL DEFAULT 'open',  -- open | running | finished | cancelled
    created_by TEXT NOT NULL,          -- 创建人 QQ 号（TEXT）
    signup_deadline TEXT,            -- 报名截止（到点自动开始；人数不足则取消）
    deadline TEXT,                   -- 活动截止（到点强制结束归档；匹配必填，接龙可选）
    hours_per_user REAL,               -- relay: 每人时限小时（默认 48）
    created_at TEXT NOT NULL,
    finished_at TEXT,
    pre_deadline_notified INTEGER NOT NULL DEFAULT 0,  -- 截止前24h进度提醒已发
);

CREATE TABLE activity_members (
    activity_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,             -- QQ 号（TEXT）
    nickname TEXT NOT NULL,            -- 入群名片/昵称
    seq INTEGER NOT NULL DEFAULT 0,    -- relay 链序 / match 环序
    next_user_id TEXT,                 -- match: 下家（匿名转发目标）
    status TEXT NOT NULL DEFAULT 'pending', -- pending|done|skipped|missed|left
    received_at TEXT,                  -- relay: 作品转交时刻（第一棒=开始通知时刻）
    submitted_at TEXT,
    content TEXT,                      -- 作品文字
    images TEXT,                       -- 作品图片文件名 JSON 数组
    PRIMARY KEY (activity_id, user_id)
);
```

- 数据管理在 `core/db/activity.py`（`ActivityManager`），DDL 在 `core/db/_base.py`
- 结束/取消时归档到 `server_data/activity_archive/<id>/`（meta.json + markdown + imgs/），Web 端 `/archive` 只读展示
- **user_id 为 TEXT**（与 `user_assets` 一致，例外于"新表统一 INTEGER"约定）

---

## 时间线

### `timeline_events`

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | TEXT | PRIMARY KEY | 事件 id（发送方生成，含随机 uuid） |
| `source` | TEXT | NOT NULL, UNIQUE(source, id), UNIQUE(source, dedup_key) | 事件来源（checkin/forum/tools/timeline…，见 `specs/timeline-protocol.md`） |
| `received_at` | TEXT | NOT NULL | 入库时间（keyset 分页游标 `received_at DESC, id DESC`） |
| `actor_id` | TEXT | NOT NULL | 行为主体（`{id:<user_id>}` 占位符解析昵称/头像） |
| `actor_qq` | TEXT | | 预留绑定外部账号 |
| `target_type` / `target_url` | TEXT | | 卡片链接 |
| `title` | TEXT | NOT NULL | 卡片标题 |
| `description` / `data` | TEXT | | 描述 / 附加 JSON（图片等） |
| `dedup_key` | TEXT | | 去重键（粒度=业务动作实例，重发同 key 撤回） |

## 时间线（未读/已读状态）

### `timeline_user_watermarks`

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `user_id` | TEXT | PRIMARY KEY | 用户 QQ 号（web 侧 str） |
| `position` | INTEGER | NOT NULL | 未读边界 rowid：首访基线或整批追平后的最大 rowid；空时间线为 0 |

### `timeline_read_events`

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `user_id` | TEXT | PRIMARY KEY (with event_id) | 用户 QQ 号 |
| `event_id` | TEXT | PRIMARY KEY (with user_id), FK→`timeline_events(id)` ON DELETE CASCADE | 已读事件 id |

- 未读判定：事件 rowid > `position` 且无回执；不依赖 `received_at`/`id` 组合（秒级精度 + 随机 uuid）
- 硬删除事件时回执级联清理；DDL 在 `core/db/_base.py::init_schema`，读写 `core/db/timeline.py::TimelineManager`

---

## 消息日志（独立库 message_log.db）

| 表 | 说明 |
|----|------|
| `messages` | 群消息日志，独立库 `server_data/message_log.db`，永久保留 |

### `messages`

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增主键 |
| `group_id` | INTEGER | NOT NULL | 群号 |
| `user_id` | INTEGER | NOT NULL | 发送者 QQ 号 |
| `msg_id` | INTEGER | UNIQUE | QQ 消息 ID，防重复入库 |
| `reply_to_msg_id` | INTEGER | 可空 | 本消息回复的目标消息 ID（reply 段剥离前落库） |
| `sent_at` | TEXT | NOT NULL | `YYYY-MM-DD HH:MM:SS` |
| `text` | TEXT | NOT NULL DEFAULT '' | 剥离 CQ 码后的纯文本（命令也存，统计时过滤） |
| `has_image` | INTEGER | NOT NULL DEFAULT 0 | 是否含图片段 |

- 索引：`idx_messages_group_time (group_id, sent_at)`、`idx_messages_text (text)`
- 只记群消息；bot 自身消息不落库

## 周报归档

### `weekly_reports`

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `week_key` | TEXT | PRIMARY KEY (week_key, group_id) | 周一日期 `YYYY-MM-DD`（周界起点） |
| `group_id` | INTEGER | PRIMARY KEY (week_key, group_id) | 群号（预留多群） |
| `data_json` | TEXT | NOT NULL | 完整版面数据 JSON |
| `created_at` | TEXT | NOT NULL | 生成时间 |

期号 = `SELECT COUNT(*) FROM weekly_reports WHERE group_id=? AND week_key <= ?`。

## 谁是卧底统计

### `user_game_stats`

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `user_id` | TEXT | PRIMARY KEY | 用户 QQ 号 |
| `total_games` | INTEGER | NOT NULL DEFAULT 0 | 累计参加场数 |
| `total_wins` | INTEGER | NOT NULL DEFAULT 0 | 累计获胜场数 |
| `civilian_wins` | INTEGER | NOT NULL DEFAULT 0 | 平民方获胜场数 |
| `spy_wins` | INTEGER | NOT NULL DEFAULT 0 | 卧底方获胜场数 |

累计成就称号（301-309）的判定数据源，读写 `plugins/who_is_spy/`。

## 议事厅

DDL 全部在 `core/db/_base.py`，业务读写 `core/db/forum.py`；`user_id` 均为 TEXT（web 侧 `get_current_user_id` 直写）。

### `forum_posts`

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 帖子 id（时间线事件 key `forum_post:{id}`） |
| `author_user_id` | TEXT | NOT NULL | 作者 QQ 号 |
| `type` | TEXT | NOT NULL | `article` / `notice` / `poll` |
| `title` | TEXT | NOT NULL | 标题 |
| `body_json` | TEXT | NOT NULL DEFAULT '' | Tiptap 富文本 JSON |
| `status` | TEXT | NOT NULL DEFAULT 'open' | open / deleted |
| `pinned` | INTEGER | NOT NULL DEFAULT 0 | 置顶（列表排序 `pinned DESC, id DESC`） |
| `created_at` / `updated_at` | TEXT | NOT NULL | 时间戳 |
| `notified_at` | TEXT | | 群通知时刻（`forum_notify` 取 `IS NULL` 的发通知） |
| `poll_anonymous` | INTEGER | NOT NULL DEFAULT 0 | 投票匿名 |
| `poll_deadline` | TEXT | | 投票截止（过期自动关闭） |

### `forum_polls`（多子投票，1.15.0）

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 子投票 id |
| `post_id` | INTEGER | NOT NULL, FK→forum_posts ON DELETE CASCADE | 所属帖子 |
| `title` | TEXT | NOT NULL DEFAULT '' | 子投票问题 |
| `allow_multi` | INTEGER | NOT NULL DEFAULT 0 | 0=单选（一人一票）/ 1=多选（可投多个选项，同选项不重复） |
| `ord` | INTEGER | NOT NULL | 展示顺序 |

> 旧列 `forum_posts.poll_allow_multi` 已废弃；旧库经 `_migrate_forum_polls` 自动迁移（选项重挂子投票、投票重映射、唯一约束改 `(poll_id, option_id, user_id)`）。

### `forum_poll_options`

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 选项 id |
| `poll_id` | INTEGER | NOT NULL, FK→forum_polls ON DELETE CASCADE | 所属子投票 |
| `text` | TEXT | NOT NULL | 选项文案 |
| `ord` | INTEGER | NOT NULL | 展示顺序 |

### `forum_poll_votes`

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `poll_id` | INTEGER | NOT NULL, UNIQUE(poll_id, option_id, user_id) | 子投票 |
| `option_id` | INTEGER | NOT NULL, FK→forum_poll_options ON DELETE CASCADE | 选项 |
| `user_id` | TEXT | NOT NULL | 投票人 |
| `created_at` | TEXT | NOT NULL | 时间戳 |

### `forum_comments`（两级嵌套回复链，1.20.0）

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 评论 id（时间线事件 key `forum_comment:{id}`） |
| `post_id` | INTEGER | NOT NULL, FK→forum_posts ON DELETE CASCADE | 所属帖子 |
| `author_user_id` | TEXT | NOT NULL | 作者 |
| `body_text` | TEXT | NOT NULL | 纯文本 |
| `status` | TEXT | NOT NULL DEFAULT 'open' | open / deleted（软删占位：有存活回复的删除保留占位与回复链） |
| `parent_id` | INTEGER | ALTER 加列 | 直接回复目标（顶层评论为 NULL） |
| `root_id` | INTEGER | ALTER 加列 | 所属顶层评论（分组键；回复的回复仍指顶层，UI 标注「回复 @某人」） |
| `created_at` | TEXT | NOT NULL | 时间戳 |
| `edited_at` | TEXT | ALTER 加列 | 编辑时间（显示「已编辑」） |

> 分页：顶层评论 `id DESC` keyset，replies 串内 `id ASC`；回复目标不存在/跨帖/已软删 → 400。

### `forum_tags` / `forum_post_tags`

```sql
CREATE TABLE forum_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE forum_post_tags (
    post_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (post_id, tag_id),
    FOREIGN KEY (post_id) REFERENCES forum_posts(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES forum_tags(id) ON DELETE CASCADE
);
```

> tag 列表仅返回被引用 tag（count>0）；删帖/编辑后引用归零的悬空 tag 自动删除。

## 工具箱

DDL 在 `core/db/_base.py`，读写 `core/db/tools.py`；图片解析兜底 `webapp/tools/icon.py`。

### `tools_links`

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 卡片 id |
| `title` / `description` / `url` / `domain` | TEXT | NOT NULL | 链接信息（domain 供图标解析） |
| `created_by` | TEXT | NOT NULL | 提交者 QQ 号（仅本人可编辑/删除） |
| `created_at` | TEXT | NOT NULL | 时间戳 |
| `click_count` | INTEGER | NOT NULL DEFAULT 0 | 点击统计（公开计数） |

### `tools_tags` / `tools_link_tags`

```sql
CREATE TABLE tools_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE tools_link_tags (
    link_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (link_id, tag_id),
    FOREIGN KEY (link_id) REFERENCES tools_links(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tools_tags(id) ON DELETE CASCADE
);
```

> tag 提交时逗号分隔自由创建（create-or-get），每链接 ≤10 个、每个 ≤20 字；页面展示 tag 云（全部 tag 及使用数量）。

### `tools_icon_cache`

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `domain` | TEXT | PRIMARY KEY | 域名 |
| `bytes` | BLOB | | 图标二进制（服务端抓首页 `<link rel=icon>` 解析） |
| `content_type` | TEXT | | MIME |
| `fetched_at` | TEXT | NOT NULL | 抓取时间 |
| `not_found` | INTEGER | NOT NULL DEFAULT 0 | 无图标负缓存（7 天） |

## 抽奖流水（周报统计用）

### `lottery_draw_log`

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增主键 |
| `user_id` | INTEGER | NOT NULL | 抽奖用户 QQ 号 |
| `drawn_at` | TEXT | NOT NULL | 抽奖时间 `YYYY-MM-DD HH:MM:SS` |
| `result_type` | TEXT | NOT NULL | `points` / `title_new` / `title_duplicate` / `title_none` |
| `value` | INTEGER | 可空 | points 数值或 title_id |
| `rarity` | TEXT | 可空 | title 稀有度（title_* 时） |
| `zero_streak_after` | INTEGER | NOT NULL DEFAULT 0 | 抽后连续零奖励次数 |

- 索引：`idx_lottery_draw_log_time (drawn_at)`

## 重要约束

- **user_id 类型不一致:** `user_assets`/`user_titles` 等旧表用 TEXT，`checkin_records`/抽奖等新表用 INTEGER。新增表统一用 INTEGER；例外：web 侧由 `get_current_user_id` 直接写入的新表（如 `timeline_*`/`forum_*`/`tools_*`/`user_game_stats`）用 TEXT，与 `forum_posts.author_user_id` 一致。
- **无迁移框架:** Schema 演化通过在 `DbManager.__init__()` 中 `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` 手动执行
- **不用 DROP COLUMN / ALTER COLUMN**（旧版 SQLite 不支持）
- **事务:** 多步原子操作用 `BEGIN IMMEDIATE` + try/except/rollback
- **必须参数化查询**（`?` 占位符），禁止 f-string SQL
