# BotEro (小埃同学) 知识库

> 生成时间: 2026-07-24 | 基于完整仓库探索

---

## 0. 项目身份

**BotEro (小埃同学)** 是一个基于 OneBot v11 协议的 QQ 群聊机器人，核心功能是**打卡图库 + 积分经济 + 称号系统**，附带抽奖、商店、闹钟、FF14 新闻等辅助功能。

- **Bot QQ:** `3915014383`
- **Bot 昵称:** `小埃同学`
- **主人 QQ:** `1057613133`
- **默认群:** `296470819`
- **语言:** Python 3（纯同步、多线程）
- **数据库:** SQLite 3 (`data.db`)
- **无构建系统:** `python main.py` 是唯一入口

---

## 1. 快速参考面板

### 1.1 硬编码常量

| 常量 | 文件:行号 | 值 |
|------|----------|-----|
| WebSocket URL | `main.py:14` | `ws://127.0.0.1:3001` |
| WS Token | `main.py:15` | `123456` |
| 默认群号 | `core/context.py:14` | `296470819` |
| 超级用户 | `core/base.py:12` | `[1057613133]` |
| Bot QQ | `core/base.py:13` | `"3915014383"` |
| Bot 昵称 | `core/base.py:11` | `"小埃同学"` |
| 下载代理 | `core/utils.py:53-55` | `127.0.0.1:7890` |
| Python 数据路径 | `core/context.py:10` | `"./server_data"` |
| OneBot 数据路径 | `core/context.py:9` | `"/app/llonebot/server_data"` |
| API 超时 | `core/api.py:43` | 30 秒 |
| 周边界偏移 | `core/utils.py:13-21` | 8 小时 (08:00) |
| 重连延迟 | `main.py:67` | 5 秒 |
| 最大装备称号数 | `plugins/title.py:394` | 3 |
| 群头衔最大长度 | `plugins/set_group_title.py:32` | 10 字符 |
| 年补卡上限 | `plugins/remedy_checkin.py:14` | 4 次 |
| 周补卡费用 | `plugins/remedy_checkin.py:55` | 6 积分 |
| 单日补卡费用 | `plugins/remedy_checkin.py:106` | 2 积分 |

### 1.2 常用路径

```
./server_data/                              ← Python 文件 I/O 根目录
  record_images/<user_id>/                  ← 打卡图片缓存（按用户分目录）
  personal_records/                         ← 生成档案图片
  thumb_cache/                              ← Web 端缩略图

/app/llonebot/server_data/                  ← OneBot API 调用中使用的路径
/var/lib/docker/volumes/onebot_qq_volume/   ← Docker 卷（裸机部署时不用）
```

### 1.3 退出代码

| 指令 | 作用 | 权限 |
|------|------|------|
| `/菜单` | 显示指令菜单 | 任何人 |
| `/打卡 + 图片` | 打卡 | 任何人 |
| `/ALL` | 全量打卡图 | 任何人 |
| `/本周打卡图` | 本周打卡图（私发） | 任何人 |
| `/本周板油` | 本周打卡成员列表 | 任何人 |
| `/档案 [年份]` | 年度热力图档案 | 任何人 |
| `/排名` / `/rank` | 积分排行榜 TOP10 | 任何人 |
| `/抽奖` / `/抽卡` | 消耗积分抽奖 | 任何人 |
| `/抽卡消费 [@]` | 查询累计抽卡消费 | 任何人 |
| `/占卜` | 塔罗牌占卜 | 任何人 |
| `.rAdB` | 掷骰子 | 任何人 |
| `/随机参考` | 随机 512x512 图片 | 任何人 |
| `/FF新闻` | FF14 国服新闻 | 任何人 |
| `/商店 [商品id]` | 浏览/兑换商品 | 任何人 |
| `/称号 [子命令]` | 称号管理 | 任何人 |
| `/闹钟 …` | 闹钟管理 | 任何人 |
| `/图库密钥` | Web 图库登录密钥 | 任何人（私聊） |
| `小埃同学` | 召唤 bot | 任何人 |
| `/补卡 YYYY-MM-DD` | 周补卡（6 积分） | 任何人 |
| `/单日补卡 YYYY-MM-DD` | 单日补卡（2 积分） | 任何人 |
| `/撤回打卡` | 撤回本周打卡 | 任何人 |
| `/群头衔 [文本]` | 设置群头衔 | 任何人 |
| 回复 + `/加精` | 设精华消息 | 群管理员 |
| 回复 + `/删除精华` | 取消精华 | 群管理员 |
| 回复 + `/全体成员` | @全体转发 | 群管理员 |
| 回复 + `/撤回` | 代撤 bot 消息 | 任何人 |
| `/超级补卡 YYYY-MM-DD [uid]` | 免积分补卡 | 群管理员 |
| `/发金币 <数量>` | 全员发积分 | 群管理员 |
| `/刷新商店` | 手动刷新商店 | 群管理员 |
| `/数据备份` | 手动备份 | 任何人 |
| `/系统状态` | 服务器状态 | 超级用户 |
| `/更新` | git pull + 重启 | 超级用户 |

---

## 2. 架构深度解析

### 2.1 事件流

```
OneBot 服务端 (NapCat/Lagrange/LLOneBot)
    │ ws://127.0.0.1:3001
    ▼
main.py: on_message(ws, msg)
    ├── "echo" in msg → api.Echo.match(msg)     ← API 响应回传
    └── 否则:
         resolve_event_type(msg):
           "meta_event_type" in msg → "meta"
           post_type == "notice"   → "notice"
           否则                     → "message"
         │
         └── threading.Thread(plugin_pool, args=(msg, event_type))
              │
              └── for plugin_cls in context.plugin_registry:
                   plugin = plugin_cls(raw_context)    ← 新实例
                   if plugin.match(event_type):
                       plugin.handle()
```

**关键属性:**
- 每个事件触发 N 个线程（N = 已注册插件数）
- 每个线程创建**新的 Plugin 实例**（无状态共享）
- 插件之间**无执行顺序保证**
- 插件之间**无同步机制**（需自行处理并发）

### 2.2 模块依赖图

```
main.py
 ├── core.api           (WS_APP, Echo 单例)
 ├── core.context       (plugin_registry, 路径常量)
 ├── core.logger        (全局 logger)
 └── plugins            (触发自动发现 → 注册所有插件)
      └── core.base     (Plugin, TimedHeartbeatPlugin)
           ├── core.event       (Event 包装器)
           ├── core.api         (ApiWrapper — 每个插件实例一个)
           ├── core.cq          (消息段构造器)
           └── core.database_manager (DbManager — 每个插件实例一个)
                └── core.context (路径常量)

core.llm/*             ← LLM 子系统（已弃用）
core.gen_image/*       ← 图片生成（独立于 bot 进程）
checkin_gallery/*      ← Web 应用（独立进程）
```

**已知循环导入:**
- `core.api` 在 `_build_title_prefix` 方法内**延迟导入** `plugins.title` 获取称号数据

### 2.3 线程安全边界

| 组件 | 安全性 | 说明 |
|------|--------|------|
| `DbManager` 实例 | **非线程安全** | 每个实例独立 connect，勿跨线程共享 |
| `sqlite3` 写锁 | 安全 | 文件锁序列化并发写 |
| `Echo.echo_list` (deque) | 安全 | `deque` append/迭代线程安全 |
| `Queue` | 安全 | 内置线程安全 |
| `context.plugin_registry` | **只读安全** | 仅导入时写入，运行时只读 |
| `TimedHeartbeatPlugin._last_run_minute` | **需注意** | 类级字典多线程读写，依赖 GIL |

### 2.4 Echo 异步响应机制

```
call_api()                            on_message() (收到响应)
    │                                      │
    ├── echo.get() → (num, Queue)          │
    ├── WS.send({action, echo: num})       │
    ├── Queue.get(timeout=30) 阻塞      ───┤ echo.match() → Queue.put(data)
    └── 返回结果                           │
```

- 最多 **20** 个未完成 API 调用（`deque(maxlen=20)`）
- 超时 30 秒返回 `{}`

---

## 3. 插件系统

### 3.1 自动发现链

```
main.py: import plugins
  → plugins/__init__.py: _load_all_plugin_modules()
    → pkgutil.walk_packages("plugins")
      → importlib.import_module(each_module)
        → @register_plugin 装饰器执行
          → context.plugin_registry.append(cls)
```

只需在 `plugins/` 下放一个 `.py` 文件，加 `@register_plugin` 装饰器即可自动注册。

### 3.2 插件最小契约

```python
from core.base import Plugin
from core.utils import register_plugin

@register_plugin                          # 必须
class MyPlugin(Plugin):                   # 必须继承 Plugin
    name = "my_plugin"                    # 必须，唯一标识
    description = "这个插件做什么。"        # 必须，用于 LLM ToolSpec

    def match(self, event_type) -> bool:  # 必须，禁止副作用
        return self.on_full_match("/指令")

    def handle(self):                     # 必须，必须有 try/except
        try:
            self.api.send_msg(text("回复"))
        except Exception:
            logger.exception(f"插件 {self.name} 异常")
```

### 3.3 Match 辅助方法

| 方法 | 说明 |
|------|------|
| `on_message()` | event_type == "message" |
| `on_full_match(keyword)` | 消息为单条纯文本且完全等于 keyword |
| `on_full_match_any(*keywords)` | 匹配任意一个 keyword |
| `on_begin_with(keyword)` | 消息首段文本等于 keyword（用于 `/打卡` + 图） |
| `on_command(command)` | 空格分词首词匹配，设置 `self.args` |
| `on_command_any(*commands)` | 同上，匹配任意一个 |
| `super_user()` | user_id in SUPER_USER |
| `admin_user()` | super_user 或群 admin/owner |
| `should_run_on_heartbeat(event_type)` | TimedHeartbeatPlugin 的定时触发判断 |

### 3.4 插件可用的实例属性

```python
self.bot_event       # Event — 当前事件包装器
self.api             # ApiWrapper — OneBot API 客户端
self.dbmanager       # DbManager — 数据库访问
```

### 3.5 TimedHeartbeatPlugin（定时插件）

```python
@register_plugin
class MyTimedPlugin(TimedHeartbeatPlugin):
    name = "my_timed"
    description = "定时插件"
    RUN_AT = "08:00"               # 触发时间 HH:MM
    RUN_WEEKDAYS = [1]            # 可选：限定星期 (1=周一)
    RUN_ANNUAL_DATES = ["01-01"]  # 可选：限定日期

    def match(self, event_type):
        return self.should_run_on_heartbeat(event_type)
```

- 防重复：基于类级 `_last_run_minute`，同一分钟不重复触发
- RUN_WEEKDAYS 和 RUN_ANNUAL_DATES 同时设置时为 AND 逻辑

---

## 4. 完整插件目录（34 个）

### 4.1 消息指令插件

| # | 插件名 | 文件 | 触发 | 功能 |
|---|--------|------|------|------|
| 1 | `call` | `call.py` | 完全匹配 `小埃同学`/`小埃同學` | 回复"我在~" |
| 2 | `menu` | `menu.py` | 完全匹配 `/菜单`/`/菜單` | 发送 BOT_MENU_TEXT（合并转发） |
| 3 | `checkin` | `checkin.py` | begin_with `/打卡` + 图片 | 打卡：存储图片、计算奖励、解锁称号 |
| 4 | `checkin_recall` | `checkin_recall.py` | notice `group_recall` | 打卡消息被撤回时回滚记录和奖励 |
| 5 | `rollback_checkin` | `roll_back.py` | 完全匹配 `/撤回打卡` | 撤回本周最近一次打卡 |
| 6 | `remedy_checkin` | `remedy_checkin.py` | begin_with `/补卡`/`/单日补卡`/`/超级补卡` | 补卡系统（详见 8.2） |
| 7 | `all_checkin_display` | `all_checkin_display.py` | 完全匹配 `/ALL` | 显示全量打卡图和统计（合并转发） |
| 8 | `week_checkin_display` | `week_checkin_display.py` | 完全匹配 `/本周打卡图` | 本周打卡图（私发） |
| 9 | `week_list` | `week_list.py` | 完全匹配 `/本周板油` | 本周完成打卡的成员列表 |
| 10 | `personal_records` | `personal_records.py` | begin_with `/档案 [年份]` | 生成年度热力图档案卡 |
| 11 | `leaderboard` | `leaderboard.py` | 完全匹配 `/排名`/`/rank` | TOP10 积分排行榜 |
| 12 | `lottery` | `lottery.py` | begin_with `/抽奖`/`/抽卡`/`/抽卡消费` | 抽卡系统（详见 9.2） |
| 13 | `immortal_lottery` | `immortal_lottery.py` | `/仙人彩`/`下注 XXXX` + meta | 仙人彩（详见 9.3） |
| 14 | `dice` | `dice.py` | 正则 `.r\d+d\d+` | 掷 A 个 B 面骰子（最大 100/1000） |
| 15 | `divination` | `divination.py` | 完全匹配 `/占卜` | 22 张大阿尔卡那 + 正逆位 |
| 16 | `title` | `title.py` | command_any `/称号`/`/稱號` | 称号系统（详见 10） |
| 17 | `redeem_shop` | `redeem_shop.py` | command `/商店 [id]` | 积分商店（详见 9.4） |
| 18 | `group_alarm` | `group_alarm.py` | begin_with `/闹钟` + meta | 闹钟系统（详见 9.5） |
| 19 | `group_essence` | `group_essence.py` | reply + `/加精`/`/精华`/`/删除精华` | 设置/取消群精华 |
| 20 | `at_all_reply` | `at_all_reply.py` | reply + `/全体成员` | @全体转发回复内容 |
| 21 | `recall_message` | `recall_message.py` | reply + `/撤回` | 代撤回 bot 消息 |
| 22 | `set_group_title` | `set_group_title.py` | begin_with `/群头衔 [文本]` | 设置群头衔（最長 10 字） |
| 23 | `random_reference` | `random_reference.py` | 完全匹配 `/随机参考` | picsum.photos 随机 512x512 |
| 24 | `gallery_login_key` | `gallery_login_key.py` | 完全匹配 `/图库密钥`/`/网页密钥` | HMAC 登录密钥（仅私聊） |
| 25 | `ff_news` | `ff_news.py` | 完全匹配 `/FF新闻` + 心跳 | FF14 国服新闻，每小时自动推送 |
| 26 | `weekly_quest` | `weekly_quest.py` | 完全匹配 `/周常` | 查看本周打卡/抽奖任务进度 |

### 4.2 通知/请求处理

| # | 插件名 | 文件 | 触发 | 功能 |
|---|--------|------|------|------|
| 27 | `auto_friend` | `auto_friend.py` | `request_type == "friend"` | 自动同意好友请求 |
| 28 | `welcome` | `welcome.py` | `notice_type == "friend_add"` | 发送欢迎私聊消息 |

### 4.3 定时/心跳

| # | 插件名 | 文件 | 计划 | 功能 |
|---|--------|------|------|------|
| 29 | `backup` | `backup.py` | 每天 08:00 | 自动备份打卡图片到本地 |
| 30 | `shop_weekly_rotation` | `redeem_shop.py` | 每周一 08:00 | 刷新商店货架 |
| 30 | `startup_changelog` | `startup_changelog.py` | 启动后首次 meta | 发送"早上好！小埃同学开机啦" |
| 31 | `weekly_quest_reset` | `weekly_quest.py` | 每周一 08:00 | 清理过期任务进度 |

### 4.4 管理/超级用户

| # | 插件名 | 文件 | 触发 | 权限 | 功能 |
|---|--------|------|------|------|------|
| 32 | `grant_points_all` | `grant_points_all.py` | `/发金币 <数量>` | admin_user() | 全员发积分 |
| 33 | `monitor` | `monitor.py` | `/系统状态` | super_user() | 运行时间/磁盘/CPU/内存 |
| 34 | `update` | `update.py` | `/更新` | super_user() | git pull + os.execv 重启 |
| 35 | `shop_manual_refresh` | `redeem_shop.py` | `/刷新商店` | admin_user() | 手动刷新商店 |

### 4.5 插件间数据依赖

```
title.py (TITLE_DEFS, get_title_def, evaluate_and_unlock_titles)
  ├── leaderboard.py      (format_title_prefix)
  ├── checkin.py           (打卡时解锁条件称号)
  ├── lottery.py           (抽卡称号池)
  ├── week_list.py         (format_title_prefix)
  └── redeem_shop.py       (商店称号定价)

bot_menu_text.py (BOT_MENU_TEXT)
  └── menu.py              (读取菜单文本)

core.api.py (_build_title_prefix)
  └── plugins.title        (延迟导入)
```

### 4.6 废弃模块

| 目录/文件 | 状态 | 说明 |
|-----------|------|------|
| `robot/` | 废弃 | 空目录，无需整理 |
| `core/llm/` | 已弃用 | LLM 对话子系统，代码完整但未集成 |

---

## 5. 数据库 Schema（20 张表）

### 5.1 用户与积分

#### user_assets
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| user_id | TEXT | PK | QQ 号（注意：TEXT） |
| points | INTEGER | DEFAULT 0 | 当前积分 |

#### user_titles
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| user_id | TEXT | PK (with title_id) | QQ 号 |
| title_id | INTEGER | PK (with user_id) | 已解锁称号 ID |
| unlocked_at | TEXT | NOT NULL | 解锁时间 |

#### user_equipped_titles
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| user_id | TEXT | PK (with slot) | QQ 号 |
| slot | INTEGER | PK (with user_id) | 1-3 槽位 |
| title_id | INTEGER | UNIQUE(user_id, title_id) | 装备的称号 ID |

#### user_title_state (Legacy)
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| user_id | TEXT | PK | 旧版单称号，已迁移 |

### 5.2 打卡

#### checkin_records
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 记录 ID |
| user_id | INTEGER | NOT NULL | QQ 号（注意：INTEGER） |
| checkin_date | TEXT | NOT NULL | `YYYY-MM-DD HH:MM:SS` |
| content | TEXT | NOT NULL | 图片文件名 或 `"remedy_checkin"` |
| message_id | INTEGER | | QQ 消息 ID（ALTER 后加的列） |

#### user_remedy_usage
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| year | INTEGER | PK (with user_id) | 年份 |
| user_id | INTEGER | PK (with year) | QQ 号 |
| used_count | INTEGER | DEFAULT 0 | 该年补救次数 |

### 5.3 积分/奖励领取

#### user_weekly_streak_reward_claims
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| user_id | INTEGER | PK (with week_start) | |
| week_start | TEXT | PK (with user_id) | 周起始日 |
| claimed_at | TEXT | NOT NULL | |

#### user_attendance_reward_claims
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| user_id | INTEGER | PK (复合) | |
| reward_type | TEXT | PK | 如 `full_week_daily` `full_month_weekly_check` |
| period_key | TEXT | PK | 周期标识 |
| points | INTEGER | NOT NULL | |
| claimed_at | TEXT | NOT NULL | |

#### quest_progress
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| user_id | TEXT | PK (复合) | |
| quest_id | INTEGER | PK | 对应 QUEST_DEFS 中的任务 ID |
| week_key | TEXT | PK | 周一日期 `YYYY-MM-DD` |
| progress | INTEGER | DEFAULT 0 | 当前累计值 |
| completed | INTEGER | DEFAULT 0 | 是否已完成 |
| claimed_at | TEXT | | 奖励领取时间，NULL 表示未领取 |

#### quest_completion_stats
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| user_id | TEXT | PK | |
| total_completions | INTEGER | DEFAULT 0 | 累计完成任务次数，跨周不重置 |

### 5.4 抽奖

#### user_lottery_daily_stats
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| stat_date | TEXT | PK (with user_id) | |
| user_id | INTEGER | PK (with stat_date) | |
| draw_count | INTEGER | DEFAULT 0 | |

#### user_lottery_stats
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| user_id | INTEGER | PK | |
| total_spent | INTEGER | DEFAULT 0 | 累计消费积分 |

#### user_lottery_profile
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| user_id | INTEGER | PK | |
| draw_count | INTEGER | DEFAULT 0 | 累计抽卡次数 |
| duplicate_count | INTEGER | DEFAULT 0 | 重复称号次数 |
| zero_streak | INTEGER | DEFAULT 0 | 当前连续未中10连 |
| max_zero_streak | INTEGER | DEFAULT 0 | 最大连续未中10连 |
| has_hit_ten | INTEGER | DEFAULT 0 | 是否中过10点 |

### 5.5 商店

#### shop_stock
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| product_id | TEXT | PK | 商品 ID |
| stock | INTEGER | NOT NULL | -1 = 无限 |

#### shop_user_buffs
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| user_id | INTEGER | PK | |
| extra_draw_pack_until | TEXT | | 额外抽卡包到期日 |
| checkin_luck_remaining | INTEGER | DEFAULT 0 | 打卡增强次数 |
| lottery_waiver_remaining | INTEGER | DEFAULT 0 | 抽奖豁免次数 |

### 5.6 闹钟

#### group_alarms
| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | |
| group_id | INTEGER | NOT NULL | 私聊=0 |
| creator_user_id | INTEGER | NOT NULL | |
| fire_at | TEXT | NOT NULL | `YYYY-MM-DD HH:MM:SS` |
| content | TEXT | NOT NULL | |
| created_at | TEXT | NOT NULL | |
| fired | INTEGER | DEFAULT 0 | 是否已触发 |
| is_private | INTEGER | DEFAULT 0 | |
| is_recurring | INTEGER | DEFAULT 0 | |
| repeat_y/m/d | INTEGER | DEFAULT 0 | Legacy |
| recur_kind | INTEGER | DEFAULT 0 | 0=单次,1=每N日,2=每周,3=每月,4=每年 |
| recur_a/b/c | INTEGER | DEFAULT 0 | 循环参数 |

索引: `idx_group_alarms_due(fired, fire_at)`

### 5.7 消息统计

#### group_daily_message_stats
user_id, group_id, stat_date → message_count

#### user_total_message_count
user_id → message_count

### 5.8 留言簿

#### guestbook_entries
id, author_user_id, content, created_at
索引: `idx_guestbook_entries_created(created_at DESC)`

#### guestbook_likes
entry_id, user_id, created_at

### 5.9 仙人彩

#### immortal_lottery_carry (per-group 累积)
group_id → carry_4a, carry_3a, carry_2a

#### immortal_lottery_results (开奖记录)
group_id, period_key → winning_digits, bet_total, drawn_at

#### immortal_lottery_bets (投注)
id, group_id, period_key, user_id, digits, bet_bj_date, created_at
UNIQUE: (group_id, user_id, bet_bj_date)
索引: `idx_immortal_bets_period(group_id, period_key)`

#### immortal_lottery_issue (期号)
group_id, period_key → issue_code

### 5.10 重要约束

- **user_id 类型不一致:** `user_assets`/`user_titles` 等旧表用 TEXT，`checkin_records`/抽奖等新表用 INTEGER。新增表统一用 INTEGER。
- **无迁移框架:** Schema 演化通过在 `DbManager.__init__()` 中 `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` 手动执行
- **不用 DROP COLUMN / ALTER COLUMN**（旧版 SQLite 不支持）
- **事务:** 多步原子操作用 `BEGIN IMMEDIATE` + try/except/rollback
- **必须参数化查询**（`?` 占位符），禁止 f-string SQL

---

## 6. 消息系统

### 6.1 send_msg 自动路由

```python
self.api.send_msg(text("回复"))
# 自动判断:
# group_id != None → 发群聊
# 只有 user_id    → 发私聊
# 两者皆无        → fallback 到 DEFAULT_GROUP_ID
```

### 6.2 标题自动注入

`send_msg()` 内部自动调用 `_inject_titles_before_at()`，在 `@` 段前注入用户装备称号。
格式: `「称号1·称号2·称号3」@用户`
**插件严禁手动构造称号前缀。**

### 6.3 CQ 消息段构造器 (`core/cq.py`)

```python
text("文本")          # {"type": "text", "data": {"text": "文本"}}
image("file:///...")  # {"type": "image", "data": {"file": "..."}}
at(qq_number)         # {"type": "at", "data": {"qq": qq_number}}
at_all()              # {"type": "at", "data": {"qq": "all"}}
reply(msg_id)         # {"type": "reply", "data": {"id": str(msg_id)}}
forward(messages)     # [{"type": "node", "data": {"content": [...]}}]
```

### 6.4 API 返回值检查

失败哨兵值:
- 整数方法 → `0`
- 布尔方法 → `False`
- 字符串方法 → `""`
- 字典方法 → `{}`
- `call_api` 超时 → `{}`

---

## 7. 周边界（08:00 偏移）

**一"周" = 周一 08:00 → 下周一 08:00**，不是自然周 00:00。

使用 `core/utils.py:get_monday_to_monday()`:
```python
from core.utils import get_monday_to_monday
start, end = get_monday_to_monday()
# start = "2026-07-20 08:00:00"
# end   = "2026-07-27 08:00:00"
```

**同样使用 08:00 偏移的:**
- `utils.day_of_year()` — 热度图日期索引
- `database_manager.get_user_streaks()` — 连续打卡天数
- `checkin_gallery/dates.py` — Web 端结算日

**新增任何"周"相关功能必须使用此函数。**

---

## 8. 打卡系统

### 8.1 正常打卡流程 (`/打卡`)

1. 验证消息包含图片
2. 获取当前周范围 (Mon 08:00 → next Mon 08:00)
3. 判断本周是否首次打卡
4. 插入 `checkin_records`（含 `message_id`）
5. 检查打卡幸运加成（商店 buff，10% 概率 +1）
6. 调用 `evaluate_and_unlock_titles()` 解锁条件称号
7. 发送解锁通知

### 8.2 积分奖励明细

| 奖励 | 条件 | 积分 | 重复保护 |
|------|------|------|---------|
| 当月全勤 | 该月每天打卡 | +1 | `full_month_weekly_check` |
| 打卡幸运 | 商店 buff，10% 概率 | +1 | buff 次数消耗 |
| 周常任务 | 3 个打卡任务（1/3/7次） | +1/+2/+3 | `quest_progress` |
| 周常任务 | 2 个抽奖任务（3/7次） | +1/+2 | `quest_progress` |

> **变更:** 原"首次打卡 +1"和"自然周全勤 +1"已合并到周常任务系统的打卡任务中。任务通过 `on_quest_trigger()` 自动完成和发放奖励。

### 8.3 撤回打卡 (`/撤回打卡`)

- 删除本周最近一次打卡记录
- 回滚已领取的 attendance rewards（全勤/满月）
- 回滚周常任务进度（通过 `on_quest_rollback()` 回收已完成任务的积分）

### 8.4 打卡消息被撤回 (自动)

`checkin_recall.py` 监听 `notice_type == "group_recall"`，根据 `message_id` 查找并回滚打卡记录和奖励（含任务进度）。

### 8.5 补卡系统

| 指令 | 费用 | 年上限 | 效果 |
|------|------|--------|------|
| `/补卡 YYYY-MM-DD` | 6 积分 | 4 次/年 | 补该周一整周 |
| `/单日补卡 YYYY-MM-DD` | 2 积分 | 无 | 补单个日期 |
| `/超级补卡 YYYY-MM-DD [uid]` | 免费 | 无 | 管理员补卡 |

补卡记录 `content = "remedy_checkin"`，查询打卡图时排除。补卡**不会**计入周常任务进度。

### 8.6 周常任务系统

5 个硬编码任务，以 Monday 08:00 周为周期重置。任务定义在 `core/utils.py:QUEST_DEFS`。

| ID | 名称 | 触发类型 | 目标 | 奖励 |
|----|------|----------|------|------|
| 1 | 打个卡先 | checkin | 1次 | +1 |
| 2 | 三连打卡 | checkin | 3次 | +2 |
| 3 | 一周都打了 | checkin | 7次 | +3 |
| 4 | 随便抽抽 | lottery | 3次 | +1 |
| 5 | 猛猛上瘾 | lottery | 7次 | +2 |

- **自动完成**: 打卡/抽奖后 `on_quest_trigger()` 自动检查并发放积分，打卡时显示完成通知，抽奖静默。
- **进度回滚**: 撤回打卡时 `on_quest_rollback()` 回退进度，若低于已完成任务目标则回收积分。
- **查看进度**: `/周常` 命令分任务显示进度条。
- **周重置**: `WeeklyQuestResetPlugin`（TimedHeartbeatPlugin，周一 08:00）清理过期数据。

---

## 9. 经济系统

### 9.1 积分获取

- 周常任务（3个打卡 + 2个抽奖，合计最多 +9）
- 当月全勤 +1
- 打卡幸运 +1
- 抽奖随机获得
- 管理员 `/发金币` 统发

### 9.2 抽卡系统 (`/抽奖` `/抽卡`)

**成本:** 1 积分/次，每日首抽免费，商店"抽奖增强"30% 概率免单

**每日次数:**
- 今日打卡: 5 次 + 商店额外次数
- 今日未打卡: 2 次 + 商店额外次数

**概率表 (累计权重 100):**

| 概率 | 奖品 | 值 |
|------|------|-----|
| 40.0% | 积分 | 0 |
| 28.0% | 积分 | +1 |
| 10.0% | 积分 | +2 |
| 6.0% | 积分 | +3 |
| 3.0% | 积分 | +5 |
| 0.8% | 积分 | +8 |
| 0.2% | 积分 | +10 |
| 9.0% | 随机普通称号 | — |
| 2.0% | 随机稀有称号 | — |
| 1.0% | 随机传说称号 | — |

**重复称号退款:** 普通 +1, 稀有 +2, 传说 +3

**抽奖画像:** 追踪 `draw_count`, `duplicate_count`, `zero_streak`, `max_zero_streak`, `has_hit_ten`

### 9.3 仙人彩 (`/仙人彩` `下注 XXXX`)

- 投注: 周一 00:00 – 周五 23:59 (北京时间)
- 开奖: 周日 20:00 (北京时间)
- 每次投注消耗 1 积分，选 4 位数字
- 奖池分配: 1 等(4A) 60% / 2 等(3A) 25% / 3 等(2A) 15%
- 无人中奖则滚入下期累积池
- 每个群独立累积

### 9.4 积分商店 (`/商店 [product_id]`)

**每周一 08:00 自动刷新**

**轮换商品 (每周随机):**
- 随机 4 个称号
- 每个库存 2 个
- 定价: 普通 3 / 稀有 6 / 传说 10

**固定功能商品 (始终有货):**

| 商品 ID | 价格 | 描述 |
|---------|------|------|
| `fn_extra_draw_pack` | 6 | 额外抽卡包，7 日内每天 +2 次抽卡 |
| `fn_checkin_boost` | 2 | 打卡增强 10 次，每次 10% 概率 +1 积分 |
| `fn_lottery_boost` | 3 | 抽奖增强 10 次，每次 30% 概率免单 |
| `fn_lottery_refresh` | 1 | 清空今日抽卡次数 |

**交易安全:** 使用 `BEGIN IMMEDIATE` 原子事务

### 9.5 闹钟系统 (`/闹钟`)

**时间格式:**
- 相对: `X分钟后` `X小时后` `X天后` `X年后`
- 绝对: `YYYY-MM-DD HH:MM`
- 仅时间: `HH:MM`（默认今天）
- 最小提前 5 分钟

**循环类型 (recur_kind):**
- 0: 一次性
- 1: 每 N 日
- 2: 每周 (recur_a=星期几)
- 3: 每月 (recur_a=日)
- 4: 每年

**管理:** `/闹钟 一览` 查看 `/闹钟 取消 <编号>` 取消

---

## 10. 称号系统

### 10.1 称号结构 (137 个)

| ID 范围 | 数量 | 稀有度 | 来源 |
|---------|------|--------|------|
| 1–40 | 40 | 普通 | 抽奖（通用梗/FF14 基础职业/Werwolf） |
| 41–59, 60-77 | 31 | 稀有/传说 | 抽奖（高阶职业/FF14 梗） |
| 78–91 | 14 | 普通 | 抽奖（工匠/采集职业） |
| 92–132 | 41 | 普通 | 抽奖（Werwolf 角色表） |
| 201–246 | 46 | 混合 | 条件解锁（时段/日期/天数/收集/任务/抽奖统计） |

### 10.2 条件称号详情

**时段类:** 早起的鸟儿 (8-12)、下午茶 (14-16)、我下班了 (17:30-18:30)、熬夜冠军 (1-5)、压哨冲线 (周日 23:30-周一 8:00)、日界线 (23:59/00:00)、刚刚好 (00:00)

**日期类:** 劳动模范 (5-1)、愚者 (4-1)、小孩 (6-1)、程序员 (10-24)、Neko (2-22)、画画更重要 (2-14)、我在~ (8-11)、圆周率 (3-14)、回响 (MM=DD)、新年 (1-1)

**累计天数:** 规律作息 (≥30)、时间管理大师 (≥100)、打卡收藏家 (≥200)、不休息的板油 (≥365)

**称号收集:** 搜集 (≥10)、研究员 (≥20)、造物院 (≥30)、称号收藏家 (≥50)、称号大师 (≥100)、金色 (≥1 传说)、小金人 (3 传说全装)

**抽奖统计:** 重复观测 (≥1)、古典概型 (≥10)、正态分布 (≥100)、试试 (≥1)、玩 (≥10)、富有 (≥25)、上瘾 (≥50)、戒戒你好 (≥100)、沉迷抽卡 (≥200)、倾家荡产 (≥500)、无底深渊 (≥1000)、大赚 (中 10)、BUG (连 3 次 0)、致命错误 (连 10 次 0)

**周常任务:** 任务达人 (≥5)、勤勉板油 (≥15)、劳模奖章 (≥30)、任务狂人 (≥50)

### 10.3 称号管理指令

`/称号` → 帮助
`/称号 当前` → 查看已装备
`/称号 <index>` → 装备
`/称号 卸下` → 取消装备
`/称号 详情 <index>` → 称号说明
`/称号 随机` → 随机装备
`/称号 查看 @用户` → 查看他人
`/称号一览` → 已解锁列表

装备上限 **3 个**（slot 1-3）。

---

## 11. Web 图库 (checkin_gallery)

### 11.1 架构

- **独立进程:** FastAPI 应用，与 bot 主进程分开运行
- **启动:** `python -m checkin_gallery`
- **默认端口:** 8765
- **共享数据:** 只读 `data.db` + 读取打卡图片文件

### 11.2 环境变量配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BOTERO_DB_PATH` | `data.db` | 数据库路径 |
| `BOTERO_IMAGE_ROOT` | `server_data/record_images` | 图片目录 |
| `BOTERO_GALLERY_HOST` | `127.0.0.1` | 绑定地址 |
| `BOTERO_GALLERY_PORT` | `8765` | 端口 |
| `BOTERO_ONEBOT_HTTP` | `http://192.168.0.103:3000` | OneBot HTTP API |
| `BOTERO_ONEBOT_TOKEN` | `123456` | OneBot token |
| `BOTERO_GROUP_ID` | `296470819` | 昵称查询群 |
| `BOTERO_AUTH_SALT` | `BotEro-Gallery-ChangeMe` | HMAC 盐值（生产必改） |
| `BOTERO_THUMB_MAX_WIDTH` | `480` | 缩略图宽度 |
| `BOTERO_CHECKIN_MAX_IMAGES` | `9` | 单次打卡最大图数 |
| `BOTERO_CHECKIN_MAX_BYTES` | `10485760` | 单图最大字节 |

### 11.3 HMAC 认证

QQ 插件中生成密钥: `base64(HMAC-SHA256(user_id, salt)[:12]) + ":" + str(user_id)`
Web 端通过 `Authorization: Bearer <token>` 验证。

### 11.4 API 路由概览

按域: `/api/auth/*` `/api/checkins` `/api/me/*` `/api/guestbook/*` `/api/users` `/thumb/*` `/media/*`
详见 `specs/web-gallery.md`

---

## 12. 图片生成 (core/gen_image)

### 12.1 模块结构

```
core/gen_image/
  models.py           ← PersonalRecordStats 数据类
  year_heatmap.py     ← GitHub 风格年度热度图
  profile_card.py     ← 完整档案卡（头像 + 统计 + 热度图）
  avatar_helper.py    ← 圆形裁剪
  fonts.py            ← 跨平台字体加载
  heatmap_colors.py   ← 颜色映射
```

### 12.2 热度图颜色

- -1 (补救日): `(255, 223, 186)` 桃色
- 0 (无打卡): `(235, 237, 240)` 浅灰
- 1: `(198, 228, 139)` 浅绿
- 2: `(123, 201, 111)` 中绿
- 3: `(35, 154, 59)` 深绿
- >3: `(25, 97, 39)` 最深绿
- 当天高亮: `(212, 175, 55)` 金色边框

### 12.3 档案卡个人记录统计

| 属性 | 来源 |
|------|------|
| 打卡不同天数 | `len(time_map)` |
| 上传图片总数 | `len(rows)` |
| 当前/最长连续周数 | `get_user_streaks()` |
| 当前/最长连续天数 | `get_user_streaks()` |
| 当前积分 | `get_user_point()` |

### 12.4 字体回退顺序

1. Windows: msyh.ttc, msyhbd.ttc, simhei.ttf
2. Linux: wqy-microhei.ttc, NotoSansCJK-Regular.ttc
3. 裸文件名
4. PIL 默认字体

---

## 13. 开发规范

### 13.1 硬性约束

- **禁止 async/await** — 纯同步，多线程
- **禁止 f-string SQL** — 必须用 `?` 参数化查询
- **禁止相对导入** — 插件间用绝对导入
- **match() 禁止副作用** — 不发消息、不写数据库
- **handle() 必须有 try/except** — 否则线程异常静默死掉
- **周相关必须用 08:00 偏移** — `get_monday_to_monday()`
- **新增/改名指令必须更新 `bot_menu_text.py`** — 同一 commit
- **代码变更必须更新对应 spec** — 同一 commit
- **禁止在插件间导入业务逻辑类** — 导入纯数据/函数允许

### 13.2 常见 AI 错误预防清单

1. 新增插件 → 加 `@register_plugin` 了吗？
2. 新增指令 → 更新 `BOT_MENU_TEXT` 了吗？
3. `handle()` → 有 try/except 吗？
4. 数据库 → 参数化查询 `?` 了吗？
5. 新表/列 → `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ADD COLUMN` 了吗？
6. 周逻辑 → 用了 08:00 偏移吗？
7. `self.bot_event.group_id` → 检查 None 了吗？
8. `self.args` → `match()` 中调了 `on_command` 吗？
9. 新依赖 → 记录了吗？
10. `async`/`await` → 确认没引入？

### 13.3 日志与错误处理

```python
from core.logger import logger
logger.info("...")
logger.error("...")
logger.exception("...")  # 自动附带 traceback
```
格式: `[bot] %(asctime)s - %(levelname)s - %(message)s`，级别 INFO。

### 13.4 Spec 文档体系

| 文档 | 内容 | 何时查阅 |
|------|------|---------|
| `architecture.md` | 系统架构、事件流、线程模型 | 理解系统 |
| `plugins.md` | 插件开发契约、生命周期 | 新增/修改插件 |
| `plugin-catalog.md` | 全部插件注册表 | 查重、了解功能 |
| `conventions.md` | 编码约定、隐式知识 | 任何开发 |
| `database.md` | 数据库 Schema、迁移规则 | 数据库变更 |
| `onebot-protocol.md` | OneBot v11 协议、消息构造 | 消息收发 |
| `web-gallery.md` | Web 图库架构、API | Web 端开发 |
| `image-generation.md` | 图片生成子系统 | 热度图/档案卡 |
| `llm-subsystem.md` | LLM 子系统（已弃用） | 参考 |

---

## 14. 部署与运维

### 14.1 裸机 Python 部署

```bash
python main.py
```

依赖: `websocket-client` `requests` `Pillow`
可选: `psutil` (系统监控) `GitPython` (更新) `openai` (LLM，已弃用)

### 14.2 Web 图库单独部署

```bash
# 设置环境变量
export BOTERO_AUTH_SALT="your-secret-salt"
export BOTERO_ONEBOT_HTTP="http://..."
python -m checkin_gallery
```

### 14.3 备份机制

- 每天 08:00 自动备份: 下载打卡图片到 `server_data/record_images/<user_id>/`
- 手动备份: 群内发 `/数据备份`

### 14.4 更新流程

超级用户发 `/更新` → `git pull` → 有新 commit 则 `os.execv()` 重启进程

### 14.5 WebSocket 重连

断开后等 5 秒自动重连，`script_start_time` 更新。

---

## 15. 版本历史 (roadmap)

| 版本 | 内容 |
|------|------|
| 1.0 | 打卡、打卡查询、历史图查询、板油查询 |
| 1.1 | 撤回打卡、服务器状态、免 @ 打卡 |
| 1.2 | 年度/月度热力图、指令重启更新 |
| 1.3 | 周一到周一八点、自动同意好友 |
| 1.4 | 全量打卡图合并转发、数据迁移 |
| 1.5 | 补卡功能 |
| 1.6 | 积分兑换系统 |
| 1.7 | 定时插件系统、修复丢失图片 |
| 1.8 | 单日补卡、更多积分消费、称号系统 |
| 2.0 | 计划: 日志系统、事件队列重构、LLM 重构 … |
| 2.1 | 未定义 |

---

## 16. API 调用速查

### 16.1 发送消息

```python
self.api.send_msg(text("..."), at(uid), image(file))
self.api.send_group_msg(*segments)
self.api.send_private_msg(*segments)
self.api.send_forward_msg([segments_list])
```

### 16.2 获取信息

```python
self.api.get_group_member_info(user_id)     # 群成员信息
self.api.get_image(file_id)                 # 图片本地路径
self.api.get_image_url(file_id)             # 图片 URL
self.api.get_qq_avatar(user_id)             # 头像 URL
self.api.get_msg(message_id)                # 消息详情
```

### 16.3 消息操作

```python
self.api.delete_msg(message_id)             # 撤回消息
self.api.set_essence_msg(message_id)        # 加精
self.api.delete_essence_msg(message_id)     # 取消加精
```

### 16.4 群管理

```python
self.api.set_group_special_title(gid, uid, title)  # 设群头衔
self.api.get_group_album_list(gid)                  # 群相册
```

### 16.5 好友

```python
self.api.set_friend_add_request(flag, approve=True)
```

### 16.6 底层

```python
self.api.call_api("action_name", {params})  # 原始 API，30s 超时
```

---

## 17. 外部 API 清单

| API | URL | 用途 |
|-----|-----|------|
| OneBot WS | `ws://127.0.0.1:3001` | QQ 消息收发 |
| FF14 新闻 | `https://cqnews.web.sdo.com/api/news/newsList` | 新闻拉取 |
| picsum.photos | `https://picsum.photos/512` | 随机参考图 |
| DeepSeek (弃用) | `https://api.deepseek.com` | LLM 对话 |
| SiliconFlow (弃用) | `https://api.siliconflow.cn` | 嵌入向量 |

---

## 18. 探索时发现的要点（分析笔记）

### 18.1 已知技术债

- `user_id` 在数据库中类型不一致（TEXT vs INTEGER），跨表查询需 CAST
- 无配置文件，所有设置硬编码在源码中
- 无迁移框架，Schema 演化依赖手动 PRAGMA + ALTER
- 无测试框架，`test/` 下是临时测试脚本
- 部分旧表 (user_title_state, group_alarms repeat_y/m/d) 已被新设计取代但未删除
- `core/api.py` 延迟导入 `plugins.title` 存在循环依赖

### 18.2 安全注意

- Web 图库的 `AUTH_SALT` 默认值在 repo 中，生产必须通过环境变量覆盖
- `AUTH_SALT` 改变会导致所有已发出的登录密钥失效
- 下载代理 `127.0.0.1:7890` 硬编码，非标准端口

### 18.3 路径陷阱

- `context.python_data_path` (`"./server_data"`) vs `context.llonebot_data_path` (`"/app/llonebot/server_data"`)
- 用在 Python 文件 I/O 用前者，传给 OneBot API 用后者
- 用错不会报错，只会返回空/失败 — **极难排查**

### 18.4 线程模型陷阱

- Plugin 实例**每次事件都是全新的** — 不能依赖实例属性持久化状态
- 多个 Plugin 实例同时操作数据库 — 靠 SQLite 文件锁
- `TimedHeartbeatPlugin._last_run_minute` 是类级字典，依赖 GIL 保护
- 不要在插件间共享 `DbManager` 实例

### 18.5 连/抽/晶 概率速算

- 抽卡预期收益 (不含称号): (0×0.4 + 1×0.28 + 2×0.1 + 3×0.06 + 5×0.03 + 8×0.008 + 10×0.002) = 0.874 积分/次
- 每日 5 次上限 + 首抽免费 = 净支出 ≤ 4 积分
- 打卡全勤 + 首周 + 满月 ≈ 获得 3 积分
- 长期结论: 纯打卡 > 纯抽卡，需靠商店 buff 和称号退款补贴
