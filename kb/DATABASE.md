# 数据库 Schema

> 全部 20+ 张表的结构与约束
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

## 消息统计

```sql
CREATE TABLE group_daily_message_stats (
    stat_date TEXT NOT NULL,
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    message_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (stat_date, group_id, user_id)
);

CREATE TABLE user_total_message_count (
    user_id INTEGER PRIMARY KEY,
    message_count INTEGER NOT NULL DEFAULT 0
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
    theme TEXT,
    status TEXT NOT NULL DEFAULT 'open',  -- open | running | finished | cancelled
    created_by TEXT NOT NULL,          -- 创建人 QQ 号（TEXT）
    deadline TEXT,                     -- match: 'YYYY-MM-DD HH:MM:SS'
    hours_per_user REAL,               -- relay: 每人时限小时（默认 48）
    created_at TEXT NOT NULL,
    finished_at TEXT
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

## 重要约束

- **user_id 类型不一致:** `user_assets`/`user_titles` 等旧表用 TEXT，`checkin_records`/抽奖等新表用 INTEGER。新增表统一用 INTEGER。
- **无迁移框架:** Schema 演化通过在 `DbManager.__init__()` 中 `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` 手动执行
- **不用 DROP COLUMN / ALTER COLUMN**（旧版 SQLite 不支持）
- **事务:** 多步原子操作用 `BEGIN IMMEDIATE` + try/except/rollback
- **必须参数化查询**（`?` 占位符），禁止 f-string SQL
