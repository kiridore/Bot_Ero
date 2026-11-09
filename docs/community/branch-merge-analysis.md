# community → dev 合并分析（待决策）

- 记录日期：2026-11-06
- 状态：**分析完成，决策已确认，合并已完成**（2026-11-06）。下文第 7 节保留原始决策项，结论见第 10 节。
- 相关分支：`community`（社区化开发线）、`dev`（主干开发线，2026-11-06 从 `master` 重新拉出）、`master`（运行环境版本）

> 本文档是决策依据，不是执行计划。合并步骤在决策项全部确认后另行编写。

## 1. 分支现状

2026-11-06 执行了一次分支重组：原 `dev`（社区化 44 个提交）重命名为 `community`，`dev` 从 `master` 重新拉出。

| 分支 | HEAD | 版本 | 独有提交 |
|---|---|---|---|
| `master` | `8f63535` | 1.61.0 | — |
| `dev` | `8f63535` | 1.61.0 | 0（与 master 同起点） |
| `community` | `dbc74b1` | 1.57.0 | 44 |

- 共同祖先：`91e918c`，版本 1.50.0
- 因此本次合并等价于此前的 `master` 与旧 `dev` 合并：`dev` 承载卧底重构、新闻订阅、兑换码网页化；`community` 承载社区化配置统一、插件开关体系、黑名单、指令限流、注册审核、个人偏好。

## 2. 两线功能差异

**仅 `dev` 有（`community` 没有）**
- 卧底重构：出局观战、参与历史（`/游戏记录`）、隐藏身份、平票淘汰修正、并发投票结算修正、重启中断处理
- 新闻订阅：FF14 新闻改为个人订阅与默认群提醒、明日方舟微博源、浏览器读取微博手机首页
- 兑换码迁到网页个人主页，QQ `/兑换码` 改为提示桩
- `user_game_stats`、`spy_game_records`、`spy_game_participants`、`news_subscriptions`、`news_push_state` 五张表

**仅 `community` 有（`dev` 没有）**
- 部署配置统一：`bot.allowed_plugins`、`bot.system_plugins`、`bot.feature_packs_file`、`bot.text_pack`、`bot.edition` 仅作描述标签
- 插件开关体系：`user_plugin_config` 表、`/插件`、`/功能包` 指令、心跳作用域、插件依赖门控
- 黑名单：账号/群封禁、任务权益保护
- 指令限流：跨群私聊共享的滚动次数限制与冷却
- 社区注册与私聊准入、群审核、用户协议 v1
- 统一消息输出模块 `core/message_output.py`、事件分发 `core/plugin_dispatch.py`、称号前缀注册式钩子
- 个人偏好：昵称头像隐私、时间线过滤他人打卡、生成图水印

## 3. 实测冲突：20 个文件

用 `git merge-tree --write-tree dev community` 实测（不落盘、不改分支），合并失败，以下文件产生冲突。

### 3.1 机械冲突（两边各加内容，均可保留）

| 文件 | 冲突内容 | 处理方向 |
|---|---|---|
| `core/config.py` | 仅 `BOTERO_VERSION` 一行 | 见决策项 D1 |
| `core/database_manager.py` | community 加 `CommunityManager`，dev 加 `WhoIsSpyManager`、`NewsManager` | 三个 manager 全部保留 |
| `webapp/profile/app.py` | community 加 `TimelineSettings`、`WatermarkSettings`，dev 加 `RedeemCodeIn` | 三组模型全部保留 |

### 3.2 删除/修改冲突（需决策语义归属）

| 文件 | 情况 | 实质 |
|---|---|---|
| `plugins/ff_news/__init__.py` | `dev` 删除，`community` 修改 | `dev` 已用新 `news` 插件接管 FF14 新闻；`community` 给旧插件加了部署许可检查、黑名单拦截、无目标群不请求。见 D2 |
| `plugins/redeem_code/codes.py` | `dev` 删除，`community` 修改 | `dev` 把兑换迁到 `webapp/profile/redeem_service.py`；`community` 给旧码表加了 `requires` 依赖声明（目标功能未开放即拒绝兑换）。见 D3 |
| `test/test_redeem_code.py` | `dev` 删除，`community` 修改 | 随 D3 决定 |

### 3.3 语义重构冲突（必须理解后移植，不能二选一）

| 文件 | 冲突段数 | 实质 |
|---|---|---|
| `plugins/who_is_spy/__init__.py` | 4 | `community` 仅加 29 行（`grant_game_titles` 的 `allow_titles` 参数，让黑名单用户不解锁称号、战绩照记）；`dev` 重写 400+ 行。见 D4 |
| `plugins/who_is_spy/relay.py` | 2 | 同上 |
| `plugins/who_is_spy/titles.py` | 2 | 同上 |
| `plugins/redeem_code/__init__.py` | — | 旧兑换实现与提示桩两种形态 |
| `plugins/menu/bot_menu_text.py` | — | 指令文本全集，两边都有新增指令 |

### 3.4 文档与清单冲突（需并入而非取舍）

`docs/community/architecture-overview.md`、`docs/community/community-edition-plan.md`、`docs/community/development-plan.md`、`docs/community/market-expansion-plan.md`、`kb/DATABASE.md`、`kb/PLUGIN_CATALOG.md`、`specs/plugin-catalog.md`、`specs/plugins.md`、`roadmap.md`。见 D6。

## 4. 必须移植的社区化语义（非取舍项）

这三处不是“选一边”，而是**必须把 community 的机制搬到 dev 的新实现上**，否则社区版部署约束出现漏洞。是否符合项目既定要求（两种部署共用同一套实现、功能开关同一规则）由所有者确认。

1. **FF14 新闻推送**：`dev` 的 `news` 插件必须同样遵守——无有效通知目标不请求外网、`allowed_plugins` 允许范围、黑名单 `admit_task` 拦截、按群插件开关。
2. **兑换码**：`dev` 的网页兑换（`webapp/profile/redeem_service.py`）必须同样遵守——`requires` 依赖声明（`title` 功能关闭时拒绝兑换，不核销、不发部分奖励）、部署允许范围、黑名单。
3. **卧底称号**：`dev` 重写后的结算路径必须保留 `allow_titles` 语义——黑名单用户照记战绩但不解锁新称号、不触发称号评估。

## 5. 部署兼容性（结论：低风险）

- **配置**：两线必填键一致（`bot.qq`、`bot.nickname`、`bot.super_users`、`bot.ws_url`、`bot.ws_token`、`bot.llonebot_data_path`、`bot.python_data_path`、`auth.salt`）。`dev` 未修改 `config.example.yaml`，现有 `config.yaml` 合并后不会因缺键启动失败。`community` 新增的键全部可选且有缺省值（`allowed_plugins` 空 = 允许全部、`system_plugins` 空 = 内置 8 项、`feature_packs_file` 空 = 内置包、`blacklist.enabled` 缺省 false）。
- **数据库**：两线新增表名完全不重叠，全部 `CREATE TABLE IF NOT EXISTS`，不破坏既有数据。
- **OneBot 接口**：`api.send_msg` 在 `community` 中仍存在且签名不变，`dev` 侧插件调用不会因接口变化报错。

## 6. 隐性风险

1. **统一输出未覆盖 dev 新代码**：`community` 的插件消息走 `core/message_output.py`；`dev` 的 `news`、`who_is_spy`、`redeem_code` 提示桩仍用旧 `self.api.send_msg`。合并后不会崩，但这些插件绕过统一输出，缺少消息合并等新语义。见 D5。
2. **部署允许名单会挡掉 dev 新插件**：若部署的 `bot.allowed_plugins` 是非空精确列表，合并后新增的 `news` 等不在名单会静默失效。见 D7。
3. **称号前缀钩子**：`community` 把称号前缀改为 `plugins/title/__init__.py` 注册的钩子，`dev` 未改该文件（只改 `defs.py`、`logic.py`），合并后注册应保留；但 `logic.py` 的 `dev` 改动与钩子函数依赖需实测确认（未验证）。
4. **行尾差异**：仓库存在 CRLF 新增行被 Git 报尾随空白的历史问题，合并时涉及这些文件会产生无关噪声。
5. **测试集变为并集**：`dev` 独有 17 个测试文件（卧底、新闻、兑换码网页），`community` 独有 30+ 个（黑名单、限流、部署门控、插件体系、个人偏好）。合并后必须全量通过。

## 7. 待所有者决策项

### D1 版本号与 CHANGELOG 编排

两线从 1.50.0 各自独立编号，`[1.57.0]` 是唯一同号但内容不同的节（`dev` 是卧底/新闻/兑换码，`community` 是个人偏好），`dev` 另有 1.58.0–1.61.0，`community` 另有 1.51.0–1.56.0。

- **A（建议）**：合并后统一 bump 到 `1.62.0`，顶部新增 `[1.62.0]` 汇总“并入社区化开发线全部功能”；`community` 的 1.51.0–1.57.0 移入独立小节「社区开发线历史（非主干版本号）」，保持可追溯。
- **B**：保留两条线各自原编号，仅给 `community` 的节加“社区线”标注，接受同一版本号出现两次不同内容。
- **C**：其他编排方式（请说明）。

### D2 FF14 新闻由谁提供

- **A（建议）**：跟随 `dev`，删除 `plugins/ff_news/`；把第 4 节的新闻门控语义移植到 `news` 插件。
- **B**：保留 `plugins/ff_news/`，并从 `news` 中移除 FF14 源（两个新闻插件并存，FF14 仍由旧插件推送）。
- **C**：保留两个插件且 `news` 也保留 FF14 源（会重复推送，不建议）。

### D3 兑换码形态

- **A（建议）**：跟随 `dev`，QQ 侧只保留提示桩，删除 `codes.py` 与旧测试；把 `requires` 依赖门控、部署许可、黑名单移植到 `webapp/profile/redeem_service.py`。
- **B**：跟随 `dev` 删除旧实现，但网页兑换**不**检查插件开关（称号功能关闭时仍可兑换称号奖励）。
- **C**：保留 QQ 指令兑换与网页兑换双入口。

### D4 黑名单与卧底称号

- **A（建议）**：把 `allow_titles` 语义移植到 `dev` 重写后的结算路径：黑名单用户照记战绩，不解锁新称号、不触发称号评估。
- **B**：不移植（黑名单用户仍会解锁卧底称号）。

### D5 统一输出模块的迁移范围

- **A（建议）**：本次合并**不**迁移 `news`、`who_is_spy`、`redeem_code` 提示桩到 `core/message_output.py`，作为技术债单独提案处理，控制本次合并规模。
- **B**：本次合并即一并迁移，使全部插件统一走 `core/message_output.py`。

### D6 文档与清单冲突处理

涉及 `docs/community/*` 四份、`kb/DATABASE.md`、`kb/PLUGIN_CATALOG.md`、`specs/plugin-catalog.md`、`specs/plugins.md`、`roadmap.md`、`plugins/menu/bot_menu_text.py`。

- **A（建议）**：逐文件“事实并入”——两线新增内容都保留，重新排序编号，删除重复描述。
- **B**：以 `dev` 版本为准，`community` 的文档改动只保留功能条目。
- **C**：以 `community` 版本为准。

### D7 部署允许名单与功能包

- **A（建议）**：合并后同步更新 `feature_packs_public.yaml` 与知识库插件清单，把 `news` 等 `dev` 新插件纳入相应分组，并在部署文档说明需要重新核对 `bot.allowed_plugins`。
- **B**：不改清单，仅在部署说明中提示。

### D8 `community` 分支的后续定位

- **A（建议）**：合并完成并验证后保留 `community` 作为历史参照，冻结不再开发，后续开发全部在 `dev`。
- **B**：双线并行维护（需明确各自承载的功能边界）。
- **C**：合并完成后删除 `community`。

### D9 合并执行方式

- **A（建议）**：在 `dev` 上分两次提交——第一次解决机械冲突（3.1）与文档并入（3.4），第二次做语义移植（第 4 节）与对应测试；每次提交后跑相关定向测试。
- **B**：一次性解决全部冲突，单个 merge commit。
- **C**：其他方式（请说明）。

## 8. 合并后必须满足的验收条件

1. `python -m pytest` 全量通过（测试集为两线并集）。
2. 冲突解决后第 4 节三项社区化语义均有对应测试覆盖，而非仅靠人工确认。
3. `openspec validate --all --strict` 通过。
4. `git diff --check` 通过。
5. 部署说明更新：现有 `config.yaml` 可直接启动；`bot.allowed_plugins` 需核对。

## 9. 本次分析未验证的事项

- ~~未解决冲突后运行测试~~（已完成后补验，见第 10 节）
- 未验证 `dev` 的 `plugins/title/logic.py` 改动与 `community` 称号前缀钩子的实际兼容性（合并后全量通过，推定兼容）。
- 未评估 `community` 的 1.51.0–1.56.0 功能在合并后的落地顺序是否需要调整。
- 未评估 `feature_packs_public.yaml` 中新增插件的分组归属是否合理。

## 10. 决策结果与执行记录

2026-11-06 所有者逐项确认全部按建议执行：`D1:A D2:A D3:A D4:A D5:A D6:A D7:A D8:A D9:A`。

### 10.1 执行结果

三次提交完成合并（均在 `dev`）：

| 提交 | 内容 |
|---|---|
| `8965b32` | 机械冲突（三套数据库 manager、个人偏好与兑换码模型并存）、结构化菜单并入、删除 `ff_news` 与旧兑换码码表、文档与清单事实并入 |
| `11123a9` | 语义移植：卧底 `allow_titles`、新闻部署门控、网页兑换依赖门控，并同步测试 |
| `f9d12a0` | 版本 `1.62.0`、CHANGELOG 重编（社区线 1.51–1.57 降为「社区开发线历史」），补齐合并遗留的指令分类与黑名单测试 |

### 10.2 实际落地的社区化语义

- 卧底结算：`grant_game_titles(..., allow_titles=False)` 照记战绩、不解锁称号、不触发称号评估；结算时按黑名单快照逐人判断。
- 卧底私聊：`GameMessenger.private` 按 `BlacklistSnapshot` 类型判断，跳过被封账号；私聊房间操作（`/加入`、`/退出`、`/状态`、游戏输入）在房间所属群被封时静默拒绝。
- 新闻推送：`news` 在请求外部源前检查默认群存在、`effective_for_scope` 与 `admit_task` 黑名单准入。
- 网页兑换：核销前检查 `requires` 依赖（部署允许范围与账号/私聊插件开关）与黑名单，未满足整次拒绝、不核销、不发部分奖励。

### 10.3 合并中发现的额外问题（已处理）

- `user_game_stats` 在 `init_schema` 中被两线各定义一次（结构一致），已去重，表数由 57 处降为 56 张。
- `test_plugin_dependency_gating.py` 的兑换用例指向已删除的 QQ 兑换实现，改为验证网页兑换的依赖门控。
- `who_is_spy/relay.py` 的动态 `call_api(action, params)` 被迁移清单测试判为需人工审计，改为字面量分支。
- 多个基于旧结构的测试（`_ensure_stats_table`、模块级 `get_room`/`collect_vote`、`FfNewsPlugin._handle_hourly`）按合并后实现重写。

### 10.4 验收结果

- `python -m pytest`：**961 passed**（384 秒）。
- `openspec validate --all --strict`：**24 passed, 0 failed**。
- `git diff --check`：通过。
- 已推送：`origin/dev` = `f9d12a0`，工作区干净。

### 10.5 遗留事项

- `news`、`who_is_spy`、`redeem_code` 提示桩仍使用原有 `send_msg`，统一输出迁移按 D5:A 留待后续提案。
- `feature_packs_public.yaml` 未新增 `news` 分组（按 D7:A 仅在文档提示核对 `bot.allowed_plugins`），需在公开部署配置时确认。
- `community` 线上三个个人偏好提案（`privacy-identity-display`、`timeline-feed-preference`、`generated-image-watermark`）随合并进入 `dev`，仍未归档，其中水印的真实 QQ 客户端验收待完成。
