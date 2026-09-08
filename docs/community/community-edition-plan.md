# BotEro 社区版开发计划

> **文档性质**：技术实施计划（模块化拆分 + 分批释出路线），承接并落地 [architecture-overview.md](architecture-overview.md) 的耦合分析；产品/运营侧背景见 [market-expansion-plan.md](market-expansion-plan.md)，本计划只覆盖其技术落地所需子集。
> **起草日期**：2026-09-08 · 基线 1.37.2
> **决策记录**：全部关键决策已于 2026-09-08 与所有者确认（见 §1），后续变更须回写本表。

---

## 1. 决策记录（已拍板，勿臆测覆盖）

| # | 决策 | 结论 |
|---|---|---|
| D1 | 产品形态 | **自运营公开服务**：所有者自己部署社区版实例（新 QQ 号），与私有版（小埃同学/主群）并行运行、数据完全隔离；陌生人加好友、拉群使用 |
| D2 | 渠道 | **仅 QQ**（OneBot v11）；Web/其他平台适配后置 |
| D3 | 账号 | QQ 号即身份；**注册只能经 QQ 机器人**（加好友自动注册流程），无开放网页注册 |
| D4 | 多群模型 | **用户全局账户（2026-09-08 修订，原 A1 每群隔离已废弃）**：每个账号在 bot 内唯一积分账户，用户级数据（钱包/打卡/称号/周常/抽奖/商店/统计）全局一份，群 = 入口与频道；群级功能（闹钟/活动/归档）天然按群。废弃理由：每群隔离使私聊玩法失去数据上下文 |
| D5 | 代码关系 | **同一主干共存 + `bot.edition` 配置切换**（2026-09-08 确认细则；不拆仓库、不建长期分支、不开源分发）。差异只允许出现在 5 处接缝白名单（config / feature_packs / 菜单文本 / 中央门控 / 权限点），业务逻辑内禁止 `if EDITION`——已固化入 `specs/conventions.md` §双形态接缝；社区部署按 **git tag 固化**（部署 = 指定 tag + config，升级 = 显式 bump tag） |
| D6 | 社区版 v1 范围 | **纯 bot，不带 webapp**（web 全家功能后置） |
| D7 | 准入 | 自动通过好友；注册后开放私聊指令；**拉群需审核**（超管批准后群才激活） |
| D8 | 技术栈 | 不变（Python + SQLite + 单进程 + 现有插件架构） |
| D9 | 存量数据 | 新旧完全隔离，不迁移私有版数据到社区实例；用户全局账户决策（D4）下无 schema 改造，私有库零迁移 |
| D10 | 节奏 | 业余项目，尽快上线，无外部时间点 → 小批次、每批可独立上线 |
| D11 | 群自治 | **不开放**（2026-09-08）：`/插件`、`/功能包` 等全部管理/配置操作仅限 config 设定的超级用户，群主/群管理员无任何修改权限；两形态一致。审核播种后的包调整由超管远程 `/功能包 <名> [off] <群号>` 操作 |

## 2. 目标形态

```
┌─────────────────────────┐      ┌─────────────────────────┐
│ 私有部署（现状，继续跑）    │      │ 社区部署（新增）           │
│ QQ: 小埃同学 + 主群        │      │ QQ: 新号（社区 bot 名待定）  │
│ bot + webapp + data.db    │      │ 仅 bot 进程 + data.db      │
│ config.yaml（私有）        │      │ config.yaml（edition=社区） │
└─────────────────────────┘      └──────────┬──────────────┘
                                            │ 服务多个群（用户全局账户 · 群=入口）
                                 陌生人: 加好友 → 注册 → 私聊指令
                                         拉群 → 审核 → 群激活 + 默认功能包
```

- 同仓库同代码：差异只来自 `config.yaml`（`bot.edition: private|community`）与功能包/系统插件开关。
- 社区部署不跑 `python -m webapp`；涉及 web 依赖的插件（gallery_login_key/forum_notify/时间线上报）在社区配置下不启用。

## 3. 工作流

> 顺序：W3（纯重构，先清障）→ W1（准入与运营，其 register 插件依赖 W3-2 系统插件配置化，其余可并行）→ 上线批次 1；W2（多群适配核对）体量小，并入 M1 验收。规模标记：S ≤ 半天 / M = 1-2 天 / L = 3+ 天（业余 + AI 协作口径）。

### W3 · 内核净化与部署可裁剪（前置，对应耦合 C1/C4/C5/C7/C8）

不改对外行为，pytest 全绿为验收。

| 任务 | 内容 | 规模 |
|---|---|---|
| W3-1 周常引擎出 core | `QUEST_DEFS` + `on_quest_trigger/on_quest_rollback` 从 `core/utils.py` 移入 `plugins/weekly_quest/`（如 `engine.py`）；调用方（checkin / lottery / checkin_recall / roll_back）改 import；`core.utils` 只留纯工具 | M |
| W3-2 系统插件配置化 | `core/context.py::SYSTEM_PLUGINS` 改读 `config.yaml bot.system_plugins`（缺省=现值）；社区配置移除 `message_logger`、`startup_changelog` | S |
| W3-3 功能包双表 | `core/feature_packs.py` 增加社区包定义（重排：activity、redeem_code 归包；剔除 ff_news/immortal_lottery/call 等私域项），`bot.edition` 选择包表；`/功能包` 指令与监控面板随之展示对应表 | M |
| W3-4 称号注入钩子化 | `core/api.py` 对 `plugins.title` 的延迟导入改为注册式钩子：`context.register_title_prefix(fn)`，plugins.title 加载时注册；未注册则优雅降级（现状行为），消除 core→plugins 反向依赖 | S |
| W3-5 配置必填分侧 | `core/config.py` 必填集拆分：`timeline.*` 改可选（空=禁用上报，`timeline_client` 直接 no-op）；纯 bot 部署不要求 webapp 侧键。解除 C7 | S |
| W3-6 发送兜底裁剪 | `core/api.py` 三处 `DEFAULT_GROUP_ID` fallback：社区版（无默认群配置）改为记日志丢弃，不再隐式发往某个群 | S |
| W3-7 菜单双文本 | `plugins/menu/bot_menu_text.py` 增加社区版菜单常量（中性文案，去私域梗），menu 插件按 edition 选择；同步指令表测试断言 | M |
| W3-8 定时任务作用域 | 播报/结算类定时任务的目标群改为遍历 `group_registry` 已激活群（见 W1 新表）；全局型任务（商店货架轮换，库存为全局单份）单次执行即可，不再依赖单群常量 | M |

暂不动（记录理由）：`core/context.py` 内跑团/卧底运行时状态随批次 2/3 释出时再随插件迁移；`core/title_defs.py` 快照层仅 webapp 使用，社区无 webapp，保留。

### W2 · 多群适配（全局账户模型，对应 C8）

**2026-09-08 修订**：用户级数据全局唯一（现状 schema 即目标模型）——**无需 schema 改造、无需私有库迁移、私聊指令天然可用**（无群上下文问题）。群级功能（闹钟/活动/周报）本就带 group_id，多群即开即用。

| 任务 | 内容 | 规模 |
|---|---|---|
| W2-1 跨群行为核对 | 核心环节数据均 user_id 键控，多群/私聊行为与单群一致（同日多群打卡 = 同日多次打卡，现有语义不变；已核对 `has_on_date`/`count_days`/`streaks` 均用户级）；补跨群一致性测试断言 | S |
| W2-2 展示口径定稿 | 排行榜/热力图/周常进度等展示全局唯一（单一社区广场，与市场计划 D3 推荐一致）；后续如需"群内排行"，加按群成员过滤的展示层即可，不动 schema | S |

### W1 · 准入、账号与运营（D3/D7 落地，新增"社区门面"插件）

**新表**：

```sql
user_accounts(user_id PK, created_at, status)            -- 注册账户（active/banned）
group_registry(group_id PK, name, invited_by, approved_at, status)   -- 已激活群
group_requests(group_id, user_id, flag, status, created_at)          -- 入群审核队列（flag=OneBot 回执）
blacklist(scope, target_id, reason, created_at, PK(scope, target_id))-- scope ∈ user|group
```

**注册流程状态机**（新插件 `register`，吸收现有 auto_friend/welcome 职责，社区配置下替代二者）：

```
陌生人加好友 ──auto──► 通过 + 私聊发注册引导（社区简介/规则/同意方式）
  └─ 用户回复同意 /注册 ──► user_accounts 落库 + 欢迎语（含拉群引导）
       └─ 未注册者私聊：仅 register/menu 可响应（中央门控，见下）
拉群/邀请进群 ──► group_requests 入队 + 私聊通知超管（群号/群名/邀请人）
  └─ 超管 /审核 <群号> 通过 ──► OneBot approve + group_registry 激活
        + 自动启用社区默认功能包 + 群内欢迎公告
  └─ /审核 <群号> 拒绝 ──► OneBot reject
  └─ /待审 列出队列（超管）
```

| 任务 | 内容 | 规模 |
|---|---|---|
| W1-1 中央门控 | `plugin_pool` 增两道统一检查（所有插件的唯一必经点，与现有 `is_plugin_enabled` 同层）：①私聊事件且用户未注册 → 仅放行白名单插件（register/menu）；②群事件且群不在 `group_registry` → 全部跳过。一处实现，插件零感知 | M |
| W1-2 register 插件 | 上述状态机 + auto_friend/welcome 职责合并；私有配置下不注册此插件（保留旧 auto_friend/welcome） | M |
| W1-3 群审核指令 | `/审核` `/待审` 超管指令 + 激活动作（默认功能包播种复用现有 group_plugin_config 机制） | M |
| W1-4 反滥用最小集 | `/拉黑` `/解除`（用户/群，超管，写入 blacklist，门控层同一处拦截）；指令频控：同用户同指令冷却（内存 dict + Lock，重启清零可接受；升级路径：落库）。全局限速后置 | M |
| W1-5 社区配置装配 | `config.example.community.yaml` 模板：新 QQ 号、edition=community、system_plugins 裁剪、无 webapp/timeline/onebot.http、群数与单人拉群数上限（`community.max_groups`）等开关 | S |

## 4. 分批释出路线

"释出" = 在社区部署的功能包中开放该模块（同一代码库，见 D5）。每批独立可用、独立验收。

| 批次 | 内容 | 前置 | 验收 |
|---|---|---|---|
| **批次 1（MVP）** | 打卡基础包（checkin / checkin_recall / roll_back / remedy_checkin / week_checkin_display / all_checkin_display / week_list / personal_records / leaderboard）+ 经济扩展（lottery / redeem_shop / redeem_code / title / weekly_quest / grant_points_all）+ register/审核/拉黑 + menu/backup/monitor/update 运维件 | W3+W2+W1 全部完成 | 全新 QQ 号冷启动：加好友→注册→私聊打卡→拉群→审核→群内全流程跑通；同用户跨群+私聊共享唯一账户（钱包/打卡/称号/周常一致），排行榜全局一份；私有部署回归全绿 |
| **批次 2** | 休闲娱乐（group_alarm / dice / divination / random_reference）+ 活动包（activity 接龙/匹配）+ 匿名游戏（who_is_spy，战绩统计全局）+ 群管理工具（group_essence / set_group_title 等，**默认关**，需 bot 为群管理员，@全体类不释出） | 批次 1 上线稳定 | 各玩法多群场景回归（活动/闹钟天然按群；卧底房间已按群 keyed，补并发回归） |
| **批次 3** | 跑团包（trpg_dice / trpg_char / trpg_session；`core/context.py` 录制状态随插件迁出 core） | 批次 2 | 跑团录制期间其他插件抑制逻辑在多群下正确 |
| **后置（暂不排期）** | webapp 社区化（时间线/论坛/图库按群分区 + web 注册绑定）、邮件通知、内容审核（举报/处置，见市场计划 §3.2）、周报数据源站内化 | — | — |
| **不释出（社区永久排除）** | ff_news（FF14 特化）、immortal_lottery（竞彩形态+私域）、message_logger（隐私红线）、startup_changelog（私域播报）、weekly_report（依赖消息日志，待重构）、call（私域人设）、web 侧全部（gallery_login_key / forum_notify / live 等） | — | — |

## 5. 里程碑

| 里程碑 | 内容 | 出口标准 |
|---|---|---|
| **M0 清障** | W3 全部（纯重构） | pytest 全绿；私有部署行为不变；社区形态配置可加载启动（bot 单进程） |
| **M1 准入** | W1 全部 + W2 跨群核对 | 注册/审核/门控/黑名单全流程可演示；跨群一致性断言通过 |
| **M2 上线** | 批次 1 装配 | §4 批次 1 验收全过；社区实例对外放号 |
| **M3+ 扩展** | 批次 2、3 按运营反馈排期 | 每批独立验收 |

依赖：M0 → M1（register 插件依赖 W3-2，其余 W1 任务可与 W3 后半并行）→ M2。

## 6. 测试与提交约定（遵循仓库既有规范）

- 每个工作流任务独立 commit（中文 Conventional Commits，代码+测试+spec+菜单文本+CHANGELOG 同 commit）；
- 新增测试走 `test/scripts/_env.py::write_config` 隔离；W1 补**门控断言**（未注册私聊/未激活群事件被跳过），W2 补**跨群一致性断言**（同用户两群+私聊打卡，钱包/周常进度唯一）；
- schema 变更同步 `kb/DATABASE.md` + `specs/database.md`；插件/指令变更同步 `kb/PLUGIN_CATALOG.md` + `plugins/menu/bot_menu_text.py`；
- 用户可见变更 bump `BOTERO_VERSION` + CHANGELOG。

## 7. 风险与对策

| 风险 | 对策 |
|---|---|
| 公开服务的滥用（刷分小号、恶意拉群、指令轰炸） | W1-4 黑名单+冷却最小集先行；`community.max_groups` 上限；内容审核后置但**上线前在注册引导中公示社区规则** |
| 全局经济跨群共享：`grant_points_all` 若对群管理员开放，任一群管理员可凭空注入全服积分 | 社区版默认收紧为仅超管（W1-5 配置项），观察后再议开放 |
| 跨群同日多次打卡被误认为刷分 | 语义与现状"同日多次打卡"一致，不新增判定；若需限制加每日奖励上限（后置） |
| 新 QQ 号风控（频繁加好友/进群触发限制） | 运营侧：注册引导分时段放量、优先邀请制内测（先拉自己的画友群试运行 1-2 周） |
| 单人业余节奏，批次间代码漂移 | 每批完成后立即在私有部署回归一次（同代码库的免费回归环境） |
| 心跳插件绕过群启用检查（meta 不查 group_plugin_config） | W1-1 中央门控 + W3-8 定时任务作用域双保险；批次 1 仅含货架轮换一个心跳任务，面小 |

## 8. 待决问题（不阻塞 M0-M2，需在批次 2 前拍板）

1. 社区 bot 的名字与人设文案（config `bot.nickname` 已支持，菜单/欢迎语文案待定稿）——回填市场计划 §8-3；
2. 群规模与配额策略（总群数上限、单群人数下限、免费/限流策略）；
3. ~~grant_points_all（发金币）在社区版对群管理员开放还是收紧为超管~~ **已定（随本次修订）**：社区版默认仅超管（全局经济下群管理员发币=注入全服积分，见 §7）；
4. AI 生成作品政策与社区内容规范文本（市场计划 §8-4/§8-7 合规项）——纯文案，不阻塞代码；
5. 批次 2 的 who_is_spy 多群并发下的房间状态隔离回归（`context.game_rooms` 已按群 keyed，需补并发用例）。

## 9. 与既有计划的关系

- `docs/community/market-expansion-plan.md`（2026-08-23，产品/运营视角）：其 §3.1 开放注册、§3.2 内容审核、§3.7 移动端等**托管平台向**改造不在本计划范围（本计划 D1 已收敛为自运营 QQ 服务）；其 §4 功能处置表与本计划 §4 批次表对齐，冲突处以本计划为准（所有者 2026-09-08 决策更新）。
- `docs/community/architecture-overview.md`：本计划的耦合点证据来源（C1-C8 编号互相对应）。
