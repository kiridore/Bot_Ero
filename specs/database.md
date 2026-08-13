# Spec: 数据库层

> 关联规范: [conventions.md](conventions.md) | [plugins.md](plugins.md) | [web-gallery.md](web-gallery.md)
> 父文档: [CLAUDE.md](../CLAUDE.md)
> 最后更新: 2026-08-13 (新增工具箱 tools_links 表)

---

## Constraint: 连接模型

- **数据库文件:** 项目根目录的 `data.db`（SQLite3 单文件）
- **Bot 端:** 每个 `Plugin` 实例的 `self.dbmanager` 是一个新的 `DbManager()`，内部创建独立的 `sqlite3.Connection`
- **Web 端:** `webapp/gallery/repository.py` 通过 `_connect()` 上下文管理器创建独立连接
- **并发:** sqlite3 自身通过文件锁序列化写操作；多个 DbManager 实例可以同时存在
- **无连接池、无 ORM、无异步驱动**

```python
# Bot 端：插件自动拥有
self.dbmanager  # DbManager 实例

# Web 端：手动创建连接
with _connect() as conn:
    conn.execute("SELECT ...")
```

---

## Schema 完整参考

### 用户与积分

#### `user_assets`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `user_id` | TEXT | PRIMARY KEY | 用户 QQ 号（注意：TEXT 类型） |
| `points` | INTEGER | DEFAULT 0 | 当前积分 |

#### `user_equipped_titles`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `user_id` | TEXT | PRIMARY KEY (with slot) | 用户 QQ 号 |
| `slot` | INTEGER | PRIMARY KEY (with user_id) | 称号槽位（1-3） |
| `title_id` | INTEGER | UNIQUE(user_id, title_id) | 装备的称号 ID |

#### `user_titles`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `user_id` | TEXT | PRIMARY KEY (with title_id) | 用户 QQ 号 |
| `title_id` | INTEGER | PRIMARY KEY (with user_id) | 已解锁的称号 ID |
| `unlocked_at` | TEXT | NOT NULL | 解锁时间 |

#### `user_title_state` (Legacy)
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `user_id` | TEXT | PRIMARY KEY | 用户 QQ 号 |
| `equipped_title` | INTEGER | | 旧版单称号系统，已迁移到 user_equipped_titles |

### 打卡

#### `checkin_records`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 记录 ID |
| `user_id` | INTEGER | NOT NULL | 用户 QQ 号（注意：INTEGER 类型） |
| `checkin_date` | TEXT | NOT NULL | 打卡日期，格式 `YYYY-MM-DD HH:MM:SS` |
| `content` | TEXT | NOT NULL | 图片文件引用 |
| `message_id` | INTEGER | | QQ 消息 ID（ALTER TABLE 后加的列，用于撤回支持） |

- 补救打卡标记：`content = "remedy_checkin"`
- 日期格式始终为 `"YYYY-MM-DD HH:MM:SS"`（08:00 偏移在应用层应用）

#### `user_remedy_usage`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `year` | INTEGER | PRIMARY KEY (with user_id) | 年份 |
| `user_id` | INTEGER | PRIMARY KEY (with year) | 用户 QQ 号 |
| `used_count` | INTEGER | DEFAULT 0 | 该年补救次数 |

### 积分/奖励领取

#### `user_weekly_streak_reward_claims`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `user_id` | INTEGER | PRIMARY KEY (with week_start) | 用户 QQ 号 |
| `week_start` | TEXT | PRIMARY KEY (with user_id) | 周起始日 |
| `claimed_at` | TEXT | NOT NULL | 领取时间 |

#### `user_attendance_reward_claims`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `user_id` | INTEGER | PRIMARY KEY (with reward_type, period_key) | 用户 QQ 号 |
| `reward_type` | TEXT | PRIMARY KEY | 奖励类型 |
| `period_key` | TEXT | PRIMARY KEY | 周期标识 |
| `points` | INTEGER | NOT NULL | 奖励积分 |
| `claimed_at` | TEXT | NOT NULL | 领取时间 |

#### `redeem_code_usage`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `user_id` | INTEGER | PRIMARY KEY (with code) | 用户 QQ 号 |
| `code` | TEXT | PRIMARY KEY (with user_id) | 兑换码（规范化后大写，如 `TEST-CODE-TEST`） |
| `used_at` | TEXT | NOT NULL | 使用时间 |

- 兑换码系统：`/兑换码 <CODE>` 由 `plugins/redeem_code/` 处理；每用户每码仅可兑换一次，`PRIMARY KEY (user_id, code)` 保证原子防重
- 读写层：`core/db/redeem.py` 的 `RedeemManager`（`DbManager.redeem`），`claim()` 原子占位、`release()` 回调失败时回滚

### 周常任务

#### `quest_progress`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `user_id` | TEXT | PRIMARY KEY (with quest_id, week_key) | 用户 QQ 号 |
| `quest_id` | INTEGER | PRIMARY KEY (with user_id, week_key) | 任务 ID（1-5） |
| `week_key` | TEXT | PRIMARY KEY (with user_id, quest_id) | 周一日期 `"YYYY-MM-DD"` |
| `progress` | INTEGER | DEFAULT 0 | 当前进度值 |
| `completed` | INTEGER | DEFAULT 0 | 是否已完成 |
| `claimed_at` | TEXT | | 奖励领取时间 |

任务定义硬编码在 `core/utils.py` 的 `QUEST_DEFS` 中，6 个任务（打卡 3 个，抽奖 3 个）。

#### `quest_completion_stats`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `user_id` | TEXT | PRIMARY KEY | 用户 QQ 号 |
| `total_completions` | INTEGER | DEFAULT 0 | 累计完成任务次数（跨周不重置） |

每次任务完成时通过 `increment_quest_completion()` 自增，不收周清理影响。称号 238-241 基于此统计解锁。

#### `quest_weekly_clears`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `user_id` | TEXT | PRIMARY KEY (with week_key) | 用户 QQ 号 |
| `week_key` | TEXT | PRIMARY KEY (with user_id) | 周一日期 |
| `cleared_at` | TEXT | NOT NULL | 全清时间 |

每周全清时 INSERT OR IGNORE，防重复。称号 261-265 基于 COUNT 解锁。

### 抽奖

#### `user_lottery_daily_stats`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `stat_date` | TEXT | PRIMARY KEY (with user_id) | 统计日期 |
| `user_id` | INTEGER | PRIMARY KEY (with stat_date) | 用户 QQ 号 |
| `draw_count` | INTEGER | DEFAULT 0 | 当日抽奖次数 |

#### `user_lottery_stats`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `user_id` | INTEGER | PRIMARY KEY | 用户 QQ 号 |
| `total_spent` | INTEGER | DEFAULT 0 | 累计抽卡消费积分 |

#### `user_lottery_profile`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `user_id` | INTEGER | PRIMARY KEY | 用户 QQ 号 |
| `draw_count` | INTEGER | DEFAULT 0 | 累计抽卡次数 |
| `duplicate_count` | INTEGER | DEFAULT 0 | 重复称号次数 |
| `zero_streak` | INTEGER | DEFAULT 0 | 当前连续未中 10 连次数 |
| `max_zero_streak` | INTEGER | DEFAULT 0 | 最大连续未中 10 连次数 |
| `has_hit_ten` | INTEGER | DEFAULT 0 | 是否中过 10 连 |

### 商店

#### `shop_stock`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `product_id` | TEXT | PRIMARY KEY | 商品 ID |
| `stock` | INTEGER | NOT NULL | 库存，`-1` 表示不限量 |

#### `shop_user_buffs`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `user_id` | INTEGER | PRIMARY KEY | 用户 QQ 号 |
| `extra_draw_pack_until` | TEXT | | 额外抽卡包有效期截止日 |
| `checkin_luck_remaining` | INTEGER | DEFAULT 0 | 打卡增强剩余次数 |
| `lottery_waiver_remaining` | INTEGER | DEFAULT 0 | 抽奖豁免剩余次数 |

### 闹钟

#### `group_alarms`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 闹钟 ID |
| `group_id` | INTEGER | NOT NULL | 群号（私聊闹钟为 0） |
| `creator_user_id` | INTEGER | NOT NULL | 创建者 QQ 号 |
| `fire_at` | TEXT | NOT NULL | 触发时间 `YYYY-MM-DD HH:MM:SS` |
| `content` | TEXT | NOT NULL | 提醒内容 |
| `created_at` | TEXT | NOT NULL | 创建时间 |
| `fired` | INTEGER | DEFAULT 0 | 是否已触发 |
| `is_private` | INTEGER | DEFAULT 0 | 是否为私聊闹钟 |
| `is_recurring` | INTEGER | DEFAULT 0 | 是否循环 |
| `repeat_y/m/d` | INTEGER | DEFAULT 0 | (Legacy) 旧版重复参数 |
| `recur_kind` | INTEGER | DEFAULT 0 | 循环类型：0=一次性, 1=每N日, 2=每周, 3=每月, 4=每年 |
| `recur_a/b/c` | INTEGER | DEFAULT 0 | 循环参数（如每周的星期几） |

**索引:** `idx_group_alarms_due` on `(fired, fire_at)`

### 留言簿

#### `guestbook_entries`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 留言 ID |
| `author_user_id` | INTEGER | NOT NULL | 作者 QQ 号 |
| `content` | TEXT | NOT NULL | 留言内容 |
| `created_at` | TEXT | NOT NULL | 创建时间 |

**索引:** `idx_guestbook_entries_created` on `(created_at DESC)`

#### `guestbook_likes`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `entry_id` | INTEGER | PRIMARY KEY (with user_id), FK→guestbook_entries(id) | 留言 ID |
| `user_id` | INTEGER | PRIMARY KEY (with entry_id) | 点赞用户 QQ 号 |
| `created_at` | TEXT | NOT NULL | 点赞时间 |

### 工具箱

#### `tools_links`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 链接 ID |
| `title` | TEXT | NOT NULL | 标题（1-50 字） |
| `description` | TEXT | NOT NULL DEFAULT `''` | 简介（≤200 字） |
| `url` | TEXT | NOT NULL | 网页链接（须 http/https） |
| `domain` | TEXT | NOT NULL | URL 域名（小写；icon 来源 `https://<domain>/favicon.ico`，失败降级首字母） |
| `created_by` | TEXT | NOT NULL | 提交人 QQ 号（TEXT 类型，与 `activities.created_by` 约定一致） |
| `created_at` | TEXT | NOT NULL | 创建时间 `YYYY-MM-DD HH:MM:SS` |

- 列表按 `id DESC`（最新在前），表小无索引；搜索经 `LIKE ? ESCAPE '\'` 匹配标题/简介/URL（`_like_escape` 转义通配符）
- 读写层：`core/db/tools.py` 的 `ToolsManager`（`DbManager.tools`）；Web 端 `POST /api/tools` 写入，`GET /api/tools` 读取，`DELETE /api/tools/{id}` 删除（仅本人，`delete_tool` 返回 not_found/forbidden/ok）

### 仙人彩（不朽抽奖）

#### `immortal_lottery_carry`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `group_id` | INTEGER | PRIMARY KEY | 群号 |
| `carry_4a` | INTEGER | DEFAULT 0 | 4A 奖池累积 |
| `carry_3a` | INTEGER | DEFAULT 0 | 3A 奖池累积 |
| `carry_2a` | INTEGER | DEFAULT 0 | 2A 奖池累积 |

#### `immortal_lottery_results`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `group_id` | INTEGER | PRIMARY KEY (with period_key) | 群号 |
| `period_key` | TEXT | PRIMARY KEY (with group_id) | 期数标识 |
| `winning_digits` | TEXT | NOT NULL | 中奖号码 |
| `bet_total` | INTEGER | DEFAULT 0 | 总投注数 |
| `drawn_at` | TEXT | NOT NULL | 开奖时间 |

#### `immortal_lottery_bets`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 投注 ID |
| `group_id` | INTEGER | NOT NULL | 群号 |
| `period_key` | TEXT | NOT NULL | 期数标识 |
| `user_id` | INTEGER | NOT NULL | 用户 QQ 号 |
| `digits` | TEXT | NOT NULL | 投注数字 |
| `bet_bj_date` | TEXT | NOT NULL | 投注对应的北京时间日期 |
| `created_at` | TEXT | NOT NULL | 创建时间 |

**UNIQUE:** `(group_id, user_id, bet_bj_date)`
**索引:** `idx_immortal_bets_period` on `(group_id, period_key)`

#### `immortal_lottery_issue`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `group_id` | INTEGER | PRIMARY KEY (with period_key) | 群号 |
| `period_key` | TEXT | PRIMARY KEY (with group_id) | 期数标识 |
| `issue_code` | TEXT | UNIQUE | 期号编码（如 `XR-2506-AB3F`） |

### 活动

#### `activities`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 活动 ID |
| `group_id` | INTEGER | NOT NULL | 群号 |
| `type` | TEXT | NOT NULL | 活动类型：`relay`（接龙）/ `match`（匹配） |
| `title` | TEXT | NOT NULL | 活动标题 |
| `description` | TEXT | | 活动描述（可选；旧列名 `theme` 已迁移） |
| `status` | TEXT | NOT NULL DEFAULT `'open'` | `open`（报名）/ `running`（进行中）/ `finished`（已结束）/ `cancelled`（已取消） |
| `created_by` | TEXT | NOT NULL | 创建人 QQ 号（TEXT 类型） |
| `signup_deadline` | TEXT | | 报名截止时间 `YYYY-MM-DD HH:MM:SS`（到点自动开始；人数不足则取消） |
| `deadline` | TEXT | | 活动截止时间 `YYYY-MM-DD HH:MM:SS`（到点强制结束归档；匹配必填，接龙可选） |
| `hours_per_user` | REAL | | 接龙每人限时（小时，默认 48） |
| `created_at` | TEXT | NOT NULL | 创建时间 |
| `finished_at` | TEXT | | 结束时间 |
| `pre_deadline_notified` | INTEGER | NOT NULL DEFAULT `0` | 截止前 24h 进度提醒是否已发送 |

- 同一群同时只有一个进行中活动（`get_active_activity` 查 `status IN ('open','running')` 取最新）
- 数据管理在 `core/db/activity.py`（`ActivityManager`），DDL 见 `core/db/_base.py`

#### `activity_members`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `activity_id` | INTEGER | PRIMARY KEY (with user_id) | 活动 ID |
| `user_id` | TEXT | PRIMARY KEY (with activity_id) | 成员 QQ 号（TEXT 类型） |
| `nickname` | TEXT | NOT NULL | 入群名片/昵称（创建时记录） |
| `seq` | INTEGER | NOT NULL DEFAULT 0 | 接龙链序 / 匹配环序（1 起） |
| `next_user_id` | TEXT | | 匹配：下家 QQ 号（匿名转发目标） |
| `status` | TEXT | NOT NULL DEFAULT `'pending'` | `pending`（待提交）/ `done`（已提交）/ `skipped`（超时跳过）/ `missed`（截止未交）/ `left`（退出） |
| `received_at` | TEXT | | 接龙：作品转交时刻（第一棒=开始通知时刻） |
| `submitted_at` | TEXT | | 提交时间 |
| `content` | TEXT | | 作品文字内容 |
| `images` | TEXT | | 作品图片文件名 JSON 数组（`imgs/img_<seq>_<n><ext>`） |

- 结束/取消时归档到 `server_data/activity_archive/<id>/`（meta.json + markdown + imgs/），Web 端 `/archive` 只读展示

---

### 社区时间线

#### `timeline_events`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | TEXT | PRIMARY KEY | 事件 ID，格式 `<source>:<uuid>`（客户端生成） |
| `source` | TEXT | NOT NULL, UNIQUE(source, id), UNIQUE(source, dedup_key) | 事件来源（`checkin`；`quest` 已停用，新增需在 timeline-protocol.md 注册） |
| `received_at` | TEXT | NOT NULL | 服务器收件时间 `YYYY-MM-DD HH:MM:SS`（展示/排序唯一依据） |
| `actor_id` | TEXT | NOT NULL | 参与者 id（发送方体系内） |
| `actor_qq` | TEXT | | QQ 号（有值则渲染昵称头像，否则「未绑定玩家」） |
| `target_type` | TEXT | | 自由标签，无业务语义 |
| `target_url` | TEXT | | 存在且 http(s) 时渲染「»详情」按钮 |
| `title` | TEXT | NOT NULL | 动作文案，支持 `{id:<user_id>}` 占位符 |
| `description` | TEXT | | 补充说明，同样支持占位符 |
| `data` | TEXT | | 业务数据 JSON 原文，Event Server 不解析 |
| `dedup_key` | TEXT | UNIQUE(source, dedup_key) | 业务自然键（如 `checkin:123456:2026-08-10`），撤回/回滚定位用 |

- 索引：`idx_timeline_feed (received_at DESC, id DESC)`（keyset 分页）
- 幂等：`(source, id)` 与 `(source, dedup_key)` 唯一约束 + `INSERT OR IGNORE`；`dedup_key` 为 NULL 时不参与唯一
- 撤回 = 硬删除（DELETE 行）；业务回滚（`/撤回打卡`、消息撤回、周常任务回退）必须联动删除对应事件
- 协议细节见 [`timeline-protocol.md`](timeline-protocol.md)

---

## Constraint: 迁移模式 (CRITICAL)

项目**没有**迁移框架。Schema 演化通过在 `DbManager.__init__()` 中手动执行：

```python
# 模式 1：添加列
self.cur.execute("PRAGMA table_info(checkin_records)")
_cols = [row[1] for row in self.cur.fetchall()]
if "message_id" not in _cols:
    self.cur.execute("ALTER TABLE checkin_records ADD COLUMN message_id INTEGER")

# 模式 2：批量添加列
for col, ddl in (
    ("is_recurring", "ALTER TABLE group_alarms ADD COLUMN is_recurring INTEGER NOT NULL DEFAULT 0"),
    ("recur_kind",  "ALTER TABLE group_alarms ADD COLUMN recur_kind INTEGER NOT NULL DEFAULT 0"),
    ...
):
    if col not in _alarm_cols2:
        self.cur.execute(ddl)
```

**RULES:**
- 永远使用 `CREATE TABLE IF NOT EXISTS`
- 新列用 `ALTER TABLE ADD COLUMN` + `DEFAULT` 值
- **绝不**使用 `DROP COLUMN`（旧版 SQLite 不支持）
- **绝不**使用 `ALTER COLUMN`（不支持）
- 新列**必须**有 DEFAULT 值（否则现有行的值为 NULL）
- 在 `__init__` 末尾调用 `self.conn.commit()`
- 迁移在生产 `data.db` 副本上测试

---

## Constraint: 事务模式

多步原子操作使用 `BEGIN IMMEDIATE` + try/except/rollback：

```python
def redeem_shop_item(self, product_id, user_id, cost, grant_fn):
    self.cur.execute("BEGIN IMMEDIATE")
    try:
        # 1. 检查条件
        # 2. 扣积分
        # 3. 减库存
        # 4. 执行 grant_fn
        self.conn.commit()
        return True, "兑换成功"
    except Exception:
        self.conn.rollback()
        return False, "兑换失败"

def replace_entire_shop_shelf(self, product_stocks):
    self.cur.execute("BEGIN IMMEDIATE")
    try:
        self.cur.execute("DELETE FROM shop_stock")
        for pid, stock in product_stocks.items():
            self.cur.execute("INSERT INTO shop_stock ...")
        self.conn.commit()
    except Exception:
        self.conn.rollback()
        raise
```

**MUST:** 条件检查建议放在 `BEGIN IMMEDIATE` 内部以保证原子性。

---

## Constraint: 查询安全

**MUST:** 始终使用参数化查询（`?` 占位符）：

```python
# ✅ 正确
self.cur.execute("SELECT * FROM user_assets WHERE user_id = ?", (user_id,))

# ❌ 错误 — SQL 注入风险
self.cur.execute(f"SELECT * FROM user_assets WHERE user_id = {user_id}")
```

**例外:** 动态列名/表名可以通过白名单验证后拼接，因为参数化不支持：

```python
# 仅当 column 来自白名单时允许
ALLOWED_COLUMNS = {"points", "message_count"}
if column in ALLOWED_COLUMNS:
    self.cur.execute(f"SELECT {column} FROM user_assets WHERE user_id = ?", (uid,))
```

---

## Constraint: 数据约定

### user_id 类型不一致（已知问题）

| 表 | user_id 类型 |
|----|-------------|
| `user_assets` | **TEXT** |
| `user_titles` | **TEXT** |
| `user_title_state` | **TEXT** |
| `user_equipped_titles` | **TEXT** |
| `checkin_records` | **INTEGER** |
| `group_alarms` | **INTEGER** |
| `user_lottery_*` | **INTEGER** |
| `user_remedy_usage` | **INTEGER** |
| `user_*_message_*` | **INTEGER** |
| `shop_user_buffs` | **INTEGER** |
| `guestbook_*` | **INTEGER** |
| `immortal_lottery_bets` | **INTEGER** |
| `activities.created_by` | **TEXT** |
| `activity_members.user_id` | **TEXT** |
| `forum_posts.author_user_id` | **TEXT** |
| `forum_comments.author_user_id` | **TEXT** |
| `forum_poll_votes.user_id` | **TEXT** |
| `forum_tags.created_by` | **TEXT** |

### 议事厅

#### `forum_posts`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 帖子 ID |
| `author_user_id` | TEXT | NOT NULL | 作者 QQ 号（TEXT 类型） |
| `type` | TEXT | NOT NULL | `'post'` / `'announce'` / `'poll'` |
| `title` | TEXT | NOT NULL | 标题 |
| `body_json` | TEXT | NOT NULL DEFAULT '' | 长文 Tiptap JSON（公告/投票为空） |
| `status` | TEXT | NOT NULL DEFAULT 'open' | `'open'` / `'closed'` / `'hidden'` / `'deleted'` |
| `pinned` | INTEGER | NOT NULL DEFAULT 0 | 置顶（v1 字段预留） |
| `created_at` | TEXT | NOT NULL | `"YYYY-MM-DD HH:MM:SS"` |
| `updated_at` | TEXT | NOT NULL | `"YYYY-MM-DD HH:MM:SS"` |
| `notified_at` | TEXT | | bot 群消息已发时刻（NULL=待发） |
| `poll_anonymous` | INTEGER | NOT NULL DEFAULT 0 | 投票匿名（不展示投票人昵称） |
| `poll_allow_multi` | INTEGER | NOT NULL DEFAULT 0 | 投票多选（v1 固定 0） |
| `poll_deadline` | TEXT | | 投票截止时间（`NULL`=无截止） |

#### `forum_poll_options`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 选项 ID |
| `post_id` | INTEGER | NOT NULL, FK→forum_posts(id) CASCADE | 所属帖子 |
| `text` | TEXT | NOT NULL | 选项文本 |
| `ord` | INTEGER | NOT NULL | 排序 |

#### `forum_poll_votes`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `poll_id` | INTEGER | NOT NULL | 帖子 ID（投票帖） |
| `option_id` | INTEGER | NOT NULL, FK→forum_poll_options(id) CASCADE | 选项 |
| `user_id` | TEXT | NOT NULL | 投票人 QQ 号 |
| `created_at` | TEXT | NOT NULL | `"YYYY-MM-DD HH:MM:SS"` |
| `UNIQUE` | | (poll_id, user_id) | **一人一票强制** |

#### `forum_comments`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 评论 ID |
| `post_id` | INTEGER | NOT NULL, FK→forum_posts(id) CASCADE | 所属帖子 |
| `author_user_id` | TEXT | NOT NULL | 评论人 QQ 号 |
| `body_text` | TEXT | NOT NULL | 评论纯文本（无 Markdown） |
| `status` | TEXT | NOT NULL DEFAULT 'open' | `'open'` / `'deleted'` |
| `created_at` | TEXT | NOT NULL | `"YYYY-MM-DD HH:MM:SS"` |

#### `forum_tags`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | tag ID |
| `name` | TEXT | NOT NULL UNIQUE | tag 名（自由创建，名字唯一） |
| `created_by` | TEXT | NOT NULL | 创建者 QQ 号 |
| `created_at` | TEXT | NOT NULL | `"YYYY-MM-DD HH:MM:SS"` |

#### `forum_post_tags`
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `post_id` | INTEGER | NOT NULL, FK→forum_posts(id) CASCADE | 帖子 |
| `tag_id` | INTEGER | NOT NULL, FK→forum_tags(id) CASCADE | tag |
| `PRIMARY KEY` | | (post_id, tag_id) | 多对多 |

跨表查询时的处理：
```python
# 当从 INTEGER 表查询 TEXT 表时
self.cur.execute("SELECT * FROM user_assets WHERE user_id = CAST(? AS TEXT)", (uid,))

# 或统一在 Python 中转换
user_id_str = str(user_id)
```

**MUST:** 新增表时将 `user_id` 统一为 `INTEGER`，逐步消除不一致。

### 打卡标记

- 正常打卡：`content` 为图片文件名
- 补救打卡：`content = "remedy_checkin"`
- Web 端查询打卡数据时需要排除补救标记记录

### 日期格式

- `checkin_date`: `"YYYY-MM-DD HH:MM:SS"`（始终带时间）
- `fire_at`, `created_at`, `claimed_at`, `drawn_at`: `"YYYY-MM-DD HH:MM:SS"`
- 周起始日 `week_start`: `"YYYY-MM-DD 08:00:00"`
- `stat_date`: `"YYYY-MM-DD"`（不带时间）
