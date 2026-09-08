# BotEro 工程架构纵览

> **文档性质**：现状架构梳理 + 耦合点分析，为社区版模块化拆分（见 [community-edition-plan.md](community-edition-plan.md)）提供事实底座。
> **基线版本**：1.37.2（2026-09-07）· 47 插件 + webapp 11 模块 + 44 表
> **数据来源**：代码实测（行数、调用点）+ `specs/`、`kb/` 权威文档交叉核对
> **维护约定**：重大结构调整时同步更新本文

---

## 1. 全景

```
                       ┌────────────────────────────────┐
                       │  config.yaml（bot/webapp 共读） │
                       └──────────┬─────────────────────┘
                                  │ import 时加载
          ┌───────────────────────┴───────────────────────┐
          ▼                                               ▼
┌──────────────────┐  事件/HTTP   ┌──────────────────────────────┐
│  bot 进程         │◄────────────►│  webapp 进程（FastAPI 单进程） │
│  main.py          │             │  python -m webapp · :8765    │
│  WS → OneBot 服务端│             │  11 个 APIRouter + 静态站      │
│  每事件一线程      │             │  全站登录门控（HMAC 密钥）      │
│  47 插件遍历       │             │  内置监控面板 :8790（bot 侧）   │
└────────┬─────────┘             └──────────────┬───────────────┘
         │                                      │
         └──────────────┬───────────────────────┘
                        ▼
              ┌───────────────────┐   ┌──────────────────────────┐
              │ core/ 共享内核     │   │ server_data/             │
              │ db/ 16 个 manager │   │ 打卡图/角色卡/设置/归档/图标 │
              └─────────┬─────────┘   └──────────────────────────┘
                        ▼
              data.db（44 表，WAL） + message_log.db（独立库）
```

- **两个进程**：bot（纯同步多线程）与 webapp（FastAPI 单进程，禁 `--workers`），共享 `core/` 包、SQLite、`config.yaml`。
- **bot → webapp**：`core/timeline_client.py` HTTP 上报时间线事件（best-effort）；webapp 不调 bot（`core/onebot_client.py` 直接走 OneBot HTTP 拉昵称/头像）。
- **QQ 号 = 身份本体**：所有用户数据以 QQ 号为主键，昵称/头像靠 OneBot 反查，登录密钥由 bot 私聊发放（HMAC(user_id, salt)）。
- **单群假设**：`DEFAULT_GROUP_ID`（config `bot.default_group`）作为无群上下文时的兜底发送目标、周报/统计的目标群、经济池的隐含范围。

## 2. 运行时形态

### 2.1 bot 进程

| 环节 | 实现 | 要点 |
|---|---|---|
| 连接 | `main.py` → `websocket-client` → OneBot v11 WS（NapCat/Lagrange/LLOneBot） | 断线 5s 重连；重连期间 API 调用超时返回 `{}` |
| 事件分发 | `on_message` → echo 匹配 API 响应，否则**每事件起一线程** `plugin_pool` | 线程内逐一遍历全部注册插件，`match()` → `handle()`，框架层统一捕获异常 |
| 插件启用 | `context.is_plugin_enabled()` 查 `group_plugin_config`（严格白名单，新群/新部署默认全禁用） | `meta` 心跳事件**跳过启用检查**——所有定时插件恒运行 |
| API 调用 | `ApiWrapper.call_api` echo 队列阻塞 30s | deque(maxlen=20) 限制并发未决调用 |
| 定时任务 | `TimedHeartbeatPlugin`（RUN_AT / RUN_WEEKDAYS / RUN_ANNUAL_DATES） | 依赖 meta 心跳驱动，无独立调度器 |
| 监控面板 | `core/web_panel.py`（:8790） | 插件启停 + config 在线编辑，仅超管 |

### 2.2 webapp 进程

- 11 个功能域模块（timeline/gallery/guestbook/profile/trpg/alarms/activities/live/forum/tools/weekly），每模块只导出 `router`，`webapp/app.py` 统一 include。
- `login_guard` 中间件全站门控：白名单外页面 302 → `/login`，API/媒体 401；凭证 Bearer 头或 `botero_key` cookie。
- 静态：模块页面合并 `webapp/static/`（54 文件，文件名全局唯一）；共享层 `core/web/static/`（auth/nav/motion/base.css 等）挂 `/shared`。
- 原生 JS，无前端框架；主题/动效 token 全站唯一来源 `base.css :root`。

## 3. 代码结构（实测行数）

```
core/                 5505 行 —— bot 与 webapp 共享内核
  config.py             import 时强制加载 config.yaml，必填缺失即退出
  db/_base.py         664 行 —— 全部 44 表 DDL + 手动迁移（PRAGMA+ALTER）
  db/<域>.py           16 个业务 manager（checkin/points/shop/lottery/titles/
                       alarm/immortal/quest/activity/guestbook/redeem/
                       timeline/forum/tools/weekly/message_log/purge_user）
  api.py / cq.py / event.py / base.py   OneBot 协议层 + 插件基类
  utils.py             通用工具 + 周常任务引擎（业务，见 C1）
  title_defs.py        称号定义快照（从 plugins/title/defs.py 动态加载，见 C4）
  feature_packs.py     功能包定义（业务，见 C1）
  context.py           全局运行时状态 + SYSTEM_PLUGINS + 跑团/卧底游戏状态（见 C1）
  timeline_client.py / onebot_client.py / auth.py / character_store.py /
  user_settings.py / mail_client.py / web_panel.py / trpg/ / gen_image/ / llm/（弃用）
  web/                 webapp 共享层（auth_deps + static/）

plugins/              ~8200 行 —— 47 个插件，pkgutil 自动发现 + @register_plugin
webapp/               ~3100 行（app.py 134 + 11 模块 router）+ static/
test/                 pytest 进程内用例 + scripts/check_* 集成脚本 + node DOM 用例
main.py               279 行（WS 连接 + 事件分发 + 重连）
```

插件按功能包分组（`core/feature_packs.py`）：基础包（打卡系 9 个）、基础扩展包（经济/称号/周常）、休闲娱乐、匿名游戏、跑团、群管理工具；系统插件 8 个常驻（menu/group_manager/startup_changelog/backup/update/auto_friend/welcome/message_logger）。

## 4. 数据模型（44 表按域分组）

| 域 | 表 | 群作用域现状 |
|---|---|---|
| 用户与积分 | user_assets | ❌ 全局（每用户一钱包） |
| 打卡 | checkin_records、user_remedy_usage、user_weekly_streak_reward_claims、user_attendance_reward_claims | ❌ 全局（仅 is_private 标记，无 group_id） |
| 周常任务 | quest_progress、quest_completion_stats、quest_weekly_clears | ❌ 全局 |
| 称号 | user_titles、user_equipped_titles、（legacy user_title_state） | ❌ 全局 |
| 抽奖 | user_lottery_daily_stats、user_lottery_stats、user_lottery_profile、lottery_draw_log | ❌ 全局 |
| 商店 | shop_stock、shop_user_buffs | ❌ 全局 |
| 闹钟 | group_alarms | ✅ 带 group_id |
| 活动 | activities、activity_members | ✅ 带 group_id |
| 仙人彩 | immortal_lottery_carry/results/bets/issue | ✅ 带 group_id |
| 周报 | weekly_reports | ✅（PK 含 group_id，但代码硬编码 `GROUP_ID` 单群） |
| 消息日志 | messages（独立库） | ✅ 带 group_id |
| 卧底 | user_game_stats | ❌ 全局 |
| 兑换码 | redeem_code_usage | ❌ 全局 |
| 插件配置 | group_plugin_config | ✅ 天然按群 |
| 留言簿 | guestbook_entries、guestbook_likes | ❌ 站级 |
| 时间线 | timeline_events、timeline_user_watermarks、timeline_read_events | ❌ 站级单一 feed |
| 议事厅 | forum_posts/polls/poll_options/poll_votes/comments/tags/post_tags | ❌ 站级 |
| 工具箱 | tools_links/tags/link_tags/icon_cache | ❌ 站级 |

**结论：核心玩法链（打卡→积分→称号→抽奖→商店→周常）整条是用户级全局数据；web 内容域是站级全局数据。** 群隔离仅存在于闹钟/活动/仙人彩/消息日志四个域。

非 DB 存储：打卡图 `record_images/<user_id>/`、跑团角色卡/个人设置 JSON（原子写）、活动归档、周报归档、缩略图缓存——均在 `server_data/`，路径经 config 可调。

另注意：**无迁移框架**——DDL 集中 `core/db/_base.py`，演化靠 `DbManager.__init__()` 里 PRAGMA 探测 + ALTER ADD COLUMN 手工执行；user_id 类型 TEXT/INTEGER 混用（新表 INTEGER，web 侧直写表 TEXT）。

## 5. 配置体系

- 单一来源项目根 `config.yaml`（gitignore，模板 `config.example.yaml`）；`BOTERO_CONFIG` 环境变量仅用于定位文件。
- `core/config.py` **import 时** `yaml.safe_load` + 必填校验（缺失即 `sys.exit`）——见 C7。
- 必填键包含 bot/OneBot/webapp 三侧混合项：即使只跑 webapp 也必须提供 `bot.ws_url` 等；反之 bot 侧必填 `timeline.url/token`（时间线上报目标，实际是 webapp 的地址）。
- 部署可变值（QQ 号、超管、群号、盐、代理、路径、端口、live/tools/mail）全部在 config；代码内仅算法常量。

## 6. 耦合点分析（社区版拆分的直接障碍）

按拆分难度从高到低编号，处置方案见 [community-edition-plan.md](community-edition-plan.md) 对应工作流。

### C1 · `core/` 不是纯内核，内嵌业务逻辑与玩法状态

| 位置 | 内容 | 问题 |
|---|---|---|
| `core/utils.py` | `QUEST_DEFS` 周常任务定义 + `on_quest_trigger/on_quest_rollback` 积分发放引擎 | 打卡/抽奖/撤回/回滚 4 个插件经此触发任务结算——玩法规则住进了"工具层" |
| `core/context.py` | `SYSTEM_PLUGINS` 硬编码 7 个插件名；跑团录制会话、卧底游戏房间、`GAME_SYSTEM`、群角色表 | 具体玩法的运行时状态住在"全局上下文"里；系统插件集合不可按部署形态裁剪（message_logger 隐私问题无法关闭） |
| `core/feature_packs.py` | 功能包 → 插件名映射 | 发行形态定义住在内核 |
| `core/title_defs.py` | 经 importlib 动态加载 `plugins/title/defs.py`（规避循环导入的快照层） | core→plugins 反向依赖的变体 |

**影响**：任何"按模块分批释出"都绕不开这层——模块的边界currently不等于目录边界。

### C2 · 身份 = QQ 号，遍布全部数据与认证链

- 44 张表主键/外键均为 QQ 号；`core/auth.py` HMAC(user_id) 即登录 token；昵称/头像依赖 `onebot_client` 反查 OneBot。
- `user_id` 类型 TEXT/INTEGER 混用，bot 侧 int、web 侧 str。
- **影响**：社区版若引入非 QQ 身份（后续开放注册/多平台），全量表 + 认证 + 展示层都要动。已决策（2026-09）：社区版 v1 保持 QQ 单渠道，此项**暂不改造**，仅隔离新旧数据。

### C3 · Schema 单体 + 无迁移框架

- 44 表 DDL 集中一个文件（`core/db/_base.py` 664 行）；表结构变更靠手工 PRAGMA+ALTER。
- **影响**：任何 schema 演进仍需手写迁移。社区版已决策用户全局账户（D4，无追追群改造），此项近期压力解除；但后续 web 社区化（时间线/论坛按群分区）或新增玩法表时，此瓶颈重现——届时应先引入成体系迁移脚本。

### C4 · 插件横向依赖 + core↔plugins 双向依赖

```
plugins.title ← checkin / lottery / leaderboard / week_list / redeem_shop（运行时导入）
core.api ──延迟导入──► plugins.title（send_msg 的 @ 前缀注入称号）
core.utils(on_quest_trigger) ◄── checkin / lottery / checkin_recall / roll_back
webapp.profile ──► webapp.gallery.repository（CheckinImage、fetch_user_settlement_day）
```

- 称号是事实上的横切关注点（6 个插件 + 发送层依赖）；周常引擎是第二个横切点。
- **影响**：title 插件不可单独摘除；社区版需把称号注入改为可插拔钩子。

### C5 · 进程间与跨侧耦合

- bot 侧 `forum_notify`/`weekly_report` 心跳插件直接读 web 侧表（forum_posts.notified_at、message_log）；
- `timeline_client` best-effort HTTP 自 POST webapp（1.37.2 已修 async 自回环死锁）；
- 心跳插件绕过群启用检查（meta 不查 `group_plugin_config`），且 `weekly_report` 硬编码 `GROUP_ID` 单群目标。
- **影响**：社区版纯 bot 部署（不带 webapp）时，这些插件的依赖（web 表、timeline.url）必须可裁剪；定时任务的群作用域需要显式化。

### C6 · web 前端单体

- 11 模块页面合并在 `webapp/static/`（文件名全局唯一约束），共享层在 `core/web/static/`；模块无法独立带走自己的页面。
- **影响**：社区版 v1 不带 web（已决策），此项后置；但意味着 web 模块暂无"独立释出"能力。

### C7 · 配置 import 强耦合 + 必填项跨侧混合

- 任何模块 import `core.config` 都要求 `config.yaml` 就位且**三侧必填键齐全**（bot WS / OneBot HTTP / timeline / auth.salt）。
- 纯 bot 部署必填 `timeline.url/token`（webapp 地址）、纯 web 部署必填 `bot.ws_url`——部署形态不可裁剪。
- **影响**：社区版"纯 bot 无 web"部署形态直接被必填校验挡住；需按部署形态区分必填集。

### C8 · 单群假设散布

- `send_msg` 三处 fallback `DEFAULT_GROUP_ID`（无群上下文时兜底发送）；
- 心跳类播报插件（startup_changelog/weekly_report/ff_news）以单群为广播目标；
- 经济/打卡/排行隐含"一个社区一个池"。
- **影响**：多群公共服务下，fallback 语义与播报目标需要显式化；数据作用域经 2026-09-08 决策维持用户全局（唯一积分账户，现状 schema 即目标模型，见计划文档 D4/W2）。

## 7. 部署形态

**现状（私有部署，VPS）**：单机 systemd 双 unit（bot + webapp）+ Caddy 根域反代 8765 + SQLite WAL。详见 `docs/web-apps-deployment.md`。

**社区版目标形态（已决策，详见计划文档）**：同仓库同代码，另一台/另一目录独立部署——新 QQ 号、独立 config.yaml、独立 DB 与 server_data，**纯 bot 无 webapp**，对外提供多群公共服务，数据与私有部署完全隔离。
