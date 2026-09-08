# BotEro 社区版 · 开发任务拆分计划

> **文档性质**：可逐个执行/验收的细粒度任务清单，是 [community-edition-plan.md](community-edition-plan.md)（决策与工作流）的执行细化。所有任务基于 1.37.2 实际代码核对（行号与调用点已验证）。
> **用法**：按依赖顺序执行；每个任务独立 commit、独立验收；设计存疑处标 ⚠️ 待定，执行前找所有者确认。
> **起草日期**：2026-09-08 · 基线 1.37.2

---

## 0. 全局约定（每个任务默认遵守，后文不再重复）

- **Commit**：中文 Conventional Commits，一个任务 = 一个逻辑 commit（代码 + 测试 + spec + 菜单文本 + CHANGELOG 同 commit，见 `specs/conventions.md` §Commit 提交分块）；纯重构记 CHANGELOG `[未发布]` 不 bump；用户可见变更 bump `BOTERO_VERSION`。
- **测试**：进程内用例进 `test/test_*.py`（conftest 自动隔离数据路径）；新集成脚本进 `test/scripts/check_*.py`（用 `_env.py::write_config`）；路径一律 `config.X` 属性访问，禁止导入期绑定。
- **文档同步**：新增/改动指令 → `plugins/menu/bot_menu_text.py` + `kb/PLUGIN_CATALOG.md` + `specs/plugin-catalog.md`；表变更 → `kb/DATABASE.md` + `specs/database.md`；动 OneBot 协议调用 → 先查 `specs/onebot-protocol.md` 权威上游。
- **双形态接缝白名单**（详见 `specs/conventions.md` §双形态接缝）：edition 差异只允许出现在 5 处接缝——`core/config.py`、`core/feature_packs.py`、菜单文本、plugin_pool 中央门控、权限点；**业务逻辑内禁止 `if EDITION`**。社区部署按 git tag 固化，不追主干 HEAD。
- **回归**：每任务完成跑全量 `pytest`；M0 期间私有部署行为必须零变化。
- **规模**：S ≤ 半天 / M = 1-2 天（业余 + AI 协作口径）。

## 1. 任务总览与依赖图

```
M0 清障（纯重构，私有部署零行为变化）
 T0.1 配置分侧+edition ──► T0.2 发送兜底 ──► T0.3 时间线上报 no-op
 T0.4 系统插件配置化（依赖 T0.1）
 T0.5 周常引擎迁移（独立）
 T0.6 称号前缀钩子化（独立）
 T0.7 功能包双表（依赖 T0.1）
 T0.8 菜单双文本（依赖 T0.1、T0.7）
 T0.9 心跳任务作用域审计（依赖 T0.7，只修批次1范围）
M1 准入与运营
 T1.1 社区表 DDL+manager（依赖 M0 全部）
 T1.2 中央门控（依赖 T1.1）
 T1.3 register 插件（依赖 T1.1、T1.2、T0.4）
 T1.4 群审核（依赖 T1.1、T1.2、T0.4）
 T1.5 拉黑+频控（依赖 T1.2）
 T1.6 管理指令权限适配（依赖 T0.1）
 T1.7 社区配置模板（依赖 M0 全部）
 T1.8 跨群一致性测试（独立，可与 T1.2 并行）
M2 上线装配
 T2.1 私有部署回归 ─► T2.2 社区实例部署+试运行 ─► T2.3 批次1验收 ─► T2.4 运营物料
M3+ 批次2/3（上线后按 §6 粗粒度展开）
```

| 里程碑 | 任务数 | 出口标准 |
|---|---|---|
| M0 | T0.1-T0.9 | pytest 全绿；私有部署行为不变；`edition=community` 配置可冷启动 bot 单进程 |
| M1 | T1.1-T1.8 | 注册→私聊指令→拉群→审核→群激活全链路可演示；门控/频控测试过 |
| M2 | T2.1-T2.4 | community-edition-plan §4 批次 1 验收逐条通过，对外放号 |
| M3+ | §6 | 每批独立验收 |

---

## 2. M0 · 清障（W3 细化，纯重构）

### T0.1 配置分侧与 edition 引入 `M`

> 执行计划：`docs/superpowers/plans/2026-09-08-config-edition-split.md`（任务级细化，含完整测试/实现代码）

**目标**：`config.yaml` 增加 `bot.edition: private|community`（缺省 private）；必填键按部署形态拆分，社区版（纯 bot）不强制 webapp/OneBot-HTTP 侧配置。

**改动**：`core/config.py`、`config.example.yaml`、`test/test_config_loader.py`、`test/test_config_wiring.py`

**步骤**：
1. `_REQUIRED` 拆为 `_REQUIRED_BOT`（qq/nickname/super_users/ws_url/ws_token/llonebot_data_path/python_data_path/auth.salt）+ `_REQUIRED_PRIVATE`（bot.default_group、onebot.http_url、onebot.token、timeline.url、timeline.token）；`edition != "private"` 时只校验 `_REQUIRED_BOT`。
2. 新导出：`EDITION`、`SYSTEM_PLUGINS_CONF = _bot.get("system_plugins")`（T0.4 消费）、`COMMUNITY = _sec("community")` 的访问器（`community.max_groups` 缺省 50、`community.cmd_cooldown_seconds` 缺省 3）。
3. `DEFAULT_GROUP_ID` 改 `Optional[int]`：`bot.default_group` 缺省时为 `None`（`GROUP_ID` 别名跟随）；`webapp` 侧使用处（`weekly/app.py` 等）在 private edition 下语义不变。
4. `config.example.yaml` 注释标注各键的 edition 适用性。

**验收**：private 配置行为与现状完全一致；缺 `default_group/timeline/onebot.http` 的 community 配置可加载；pytest 全绿。

**commit**：`feat(配置): bot.edition 部署形态与必填键分侧`

### T0.2 发送兜底适配（DEFAULT_GROUP_ID 可空）`S`

**目标**：社区版无默认群时，无群上下文的群发不再隐式发往某个群。

**改动**：`core/api.py`（3 处：`send_group_msg` L98、`send_group_forward_msg` L171、`send_group_forward_nodes` L191 的 `if not group_id: group_id = runtime_context.DEFAULT_GROUP_ID`）

**步骤**：`DEFAULT_GROUP_ID` 为 `None` 时记 `logger.warning("无群上下文且未配置默认群，丢弃发送")` 并返回 0。私有版（有默认群）行为不变。

**测试**：`test/test_api_send_fallback.py`（新增）：mock runtime_context.DEFAULT_GROUP_ID=None，断言不发 WS 帧且返回 0。

**commit**：`fix(发送): 无默认群部署丢弃群发并告警`

### T0.3 时间线上报可关 `S`

**目标**：社区部署（无 webapp）`timeline.url/token` 留空 → `emit_event/retract_event` 直接 no-op，不再要求配置。

**改动**：`core/timeline_client.py`（模块入口判 `TIMELINE_URL`/`TIMELINE_TOKEN` 为空 → `return`），`core/config.py`（`TIMELINE_URL` 允许空串）

**测试**：现有时间线相关用例补"空配置 no-op"断言。

**commit**：`feat(时间线): 留空配置时上报静默关闭`

### T0.4 系统插件配置化 `S`

**目标**：`SYSTEM_PLUGINS` 从硬编码 frozenset 改读 `config.yaml bot.system_plugins`（缺省 = 现值 7 个），社区配置裁掉 `message_logger`、`startup_changelog`。

**改动**：`core/context.py`（`SYSTEM_PLUGINS = frozenset(config.SYSTEM_PLUGINS_CONF or 默认集)`）、`config.example.yaml`

**说明**：消费方（`main.py` plugin_pool、`group_manager` 的 🔒 展示、监控面板）全部经 `runtime_context.SYSTEM_PLUGINS` 引用，改一处数据源即全生效，无需逐处改。

**测试**：`test/test_context_system_plugins.py`：自定义 system_plugins 配置生效；不在集合内的 message_logger 类插件对 meta 事件仍运行（心跳插件绕过启用检查是既有语义，本任务不改——见 T1.2 门控兜底）。

**commit**：`feat(插件): 系统插件集合改为 config 配置`

### T0.5 周常任务引擎迁出 core `M`

**目标**：玩法规则（QUEST_DEFS、on_quest_trigger/on_quest_rollback、get_quest_week_key）从 `core/utils.py` 移入 `plugins/weekly_quest/engine.py`，core 只留纯工具。行为零变化。

**改动**：
- 新建 `plugins/weekly_quest/engine.py`：迁入 `QUEST_DEFS`、`get_quest_week_key`、`on_quest_trigger`、`on_quest_rollback`（内部继续用 `core.utils.get_monday_to_monday/add_user_point`——绝对导入，符合规范）
- 改 import（5 处）：`plugins/checkin/__init__.py:5,125`、`plugins/lottery/__init__.py:7,66`、`plugins/checkin_recall/__init__.py:6,106`、`plugins/roll_back/__init__.py:4,86`、`plugins/weekly_quest/__init__.py:3,23,30,58`
- `core/utils.py` 删除对应定义（保留 `get_monday_to_monday`、`add_user_point` 等纯工具）

**测试**：现有周常/打卡/抽奖回归全绿即证明等价；补 `test/test_quest_engine.py`（新家地址）冒烟：trigger 达标发奖、rollback 撤奖。

**commit**：`refactor(周常): 任务引擎从 core 迁入 weekly_quest 插件域`

### T0.6 称号前缀注入钩子化 `S`

**目标**：消除 `core/api.py → plugins.title` 反向依赖（`_build_title_prefix` L49-64 的延迟 import）。

**改动**：
- `core/context.py`：`TITLE_PREFIX_PROVIDER = None` + `def register_title_prefix_provider(fn)`
- `plugins/title/__init__.py`：模块级注册 `runtime_context.register_title_prefix_provider(build_title_prefix)`（把现 `_build_title_prefix` 主体迁来，含 `dbmanager.titles.equipped_all` + `get_title_def` 逻辑与异常吞掉）
- `core/api.py`：`_build_title_prefix` 改为调 `runtime_context.TITLE_PREFIX_PROVIDER(dbmanager, user_id)`，未注册返回 `""`（title 插件不在 registry 时的降级，与现状一致）

**测试**：现有 @ 提及称号注入用例回归；补"未注册 provider 时消息原样"断言。

**commit**：`refactor(称号): 前缀注入改为注册式钩子解除 core 反向依赖`

### T0.7 功能包双表与社区包定义 `M`

**目标**：功能包按 edition 选择；定义社区版包结构（剔除私域插件、补齐游离插件）。

**改动**：`core/feature_packs.py`、`plugins/group_manager/__init__.py`（4 处 `FEATURE_PACKS` → `ACTIVE_PACKS`）、`kb/PLUGIN_CATALOG.md`、`specs/plugin-catalog.md`

**社区包定义**（⚠️ 待定：包名与归组可调）：

| 包 | 插件 |
|---|---|
| 打卡基础 | checkin、checkin_recall、roll_back、remedy_checkin、week_checkin_display、all_checkin_display、week_list、personal_records、leaderboard |
| 经济扩展 | lottery、redeem_shop、redeem_code、grant_points_all、title、weekly_quest |
| 娱乐工具 | group_alarm、dice、divination、random_reference |
| 活动 | activity（现游离于任何包，补齐） |
| 匿名游戏 | who_is_spy（批次 2 开放） |
| 跑团 | trpg_dice、trpg_session、trpg_char（批次 3 开放） |
| 群管理 | group_essence、set_group_title、recall_message（批次 2，默认关；at_all_reply 不释出） |

私有包 `FEATURE_PACKS` 原样保留。社区部署默认启用"打卡基础 + 经济扩展"（T1.4 审核通过时播种）。

**测试**：`test/test_feature_packs.py`：edition 选择正确；社区包不含 ff_news/immortal_lottery/message_logger/call。

**commit**：`feat(功能包): 双形态包表与社区包定义`

### T0.8 菜单双文本 `M`

**目标**：社区版菜单中性文案（去私域梗：板油、FF14、"小埃同学"人设），按 edition 切换。

**改动**：`plugins/menu/bot_menu_text.py`（新增 `COMMUNITY_MENU_TEXT` 常量）、`plugins/menu/__init__.py`（按 `config.EDITION` 选）、菜单相关测试断言、`kb/QUICK_REFERENCE.md`（指令表标注 edition 差异）

**⚠️ 待定**：社区版收录指令清单 = 打卡基础 + 经济扩展两包的全部指令（与 T0.7 默认包一致）；文案基调（"喵"等人设语气保留与否）由所有者定稿。

**测试**：`test/test_menu_text.py`：两套文本均为合法指令超集；edition 切换生效。

**commit**：`feat(菜单): 社区版菜单文本`

### T0.9 心跳任务作用域审计（仅批次 1 范围）`S`

**目标**：确认批次 1 唯一心跳任务 `shop_weekly_rotation`（`plugins/redeem_shop/__init__.py:25`）在社区形态正确：货架全局单份 → 轮换单次执行，无需按群；`ff_news`/`startup_changelog` 等私域播报已在 T0.4/T0.7 排除。

**步骤**：逐个 grep `TimedHeartbeatPlugin` 子类 → 列"私有专属（不进社区）/全局单次（现状即可）/需按群遍历（批次 2 处理）"三栏结论表，写入 `specs/plugins.md` 附录；本任务只修"批次 1 范围内"的问题（预期为零代码改动，纯审计产出）。

**commit**：`docs(插件): 心跳任务多群作用域审计结论`

---

## 3. M1 · 准入与运营（W1+W2 细化）

### T1.1 社区表 DDL 与 manager `M`

**新表**（DDL 进 `core/db/_base.py::init_schema`，读写集中新文件 `core/db/community.py::CommunityManager`；`DbManager` 挂 `self.community`）：

```sql
user_accounts(user_id INTEGER PRIMARY KEY, created_at TEXT NOT NULL)          -- 注册即插入；封禁走 blacklist，不设 status 列（对总计划的简化）
group_registry(group_id INTEGER PRIMARY KEY, name TEXT, invited_by INTEGER,
               approved_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active')  -- status: active|removed（bot 被移出群时标记，保留记录）
group_requests(group_id INTEGER NOT NULL, user_id INTEGER NOT NULL, flag TEXT NOT NULL,
               sub_type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',   -- pending|approved|rejected
               created_at TEXT NOT NULL, PRIMARY KEY (group_id, user_id, created_at))
blacklist(scope TEXT NOT NULL, target_id INTEGER NOT NULL, reason TEXT,
          created_at TEXT NOT NULL, PRIMARY KEY (scope, target_id))             -- scope ∈ 'user'|'group'
```

**步骤**：DDL + `CommunityManager`（register_user / is_registered / upsert_request / pending_requests / resolve_request / activate_group / is_group_active / iter_active_groups / ban / unban / is_banned）+ 文档同步（`kb/DATABASE.md`、`specs/database.md`，表总数 44→48）。

**测试**：`test/test_community_db.py`：CRUD + 状态流转 + 幂等（重复注册、重复入队同 flag 去重）。

**commit**：`feat(社区): 账号/群注册/审核/黑名单表与数据层`

### T1.2 中央门控 `M`

**目标**：`plugin_pool`（`main.py:29`）在现有 `is_plugin_enabled` 检查前增加三道集中检查——黑名单 → 群激活 → 私聊注册。一处实现，全部插件零改动。

**改动**：`main.py`、`core/context.py`（新增 `PRIVATE_WHITELIST = frozenset({"register", "menu"})` 常量，⚠️ 待定集合内容）

**逻辑**（每事件**一次**查询，结果缓存供循环复用，不逐插件查）：

```python
# plugin_pool 顶部，进循环前：
if context_is_message_or_notice(raw):
    uid, gid = raw.get("user_id"), raw.get("group_id")
    if community.is_banned("user", uid) or (gid and community.is_banned("group", gid)):
        return                                  # 黑名单：整事件丢弃
    if gid is not None and not community.is_group_active(gid):
        return                                  # 未激活群：整事件丢弃（含被移出后 status=removed）
    if gid is None and not community.is_registered(uid):
        allow = {plugin_key(c) for c in registry} & PRIVATE_WHITELIST   # 未注册私聊：仅白名单插件可见
```

**边界确认**（写进代码注释）：`meta` 事件跳过全部门控（心跳必须活着）；`notice` 事件放行（register 插件靠 notice 触发）；私有 edition 下三道门控全部直通（`group_registry` 空 = 所有群不激活 → 必须给私有部署免检：**门控仅 `EDITION == "community"` 生效**，⚠️ 这是关键设计点——私有版零行为变化）。

**测试**：`test/test_gate.py`（新）：①未注册私聊仅白名单插件收到事件 ②未激活群全静默 ③黑名单用户/群全静默 ④私有 edition 直通 ⑤meta/notice 不受门控影响。

**commit**：`feat(社区): plugin_pool 中央门控（黑名单/群激活/注册检查）`

### T1.3 register 插件（注册流程）`M`

**目标**：新插件 `plugins/register/`，社区形态下承接 auto_friend + welcome 职责。

**流程**（⚠️ 文案与确认方式待所有者定稿）：

```
request_type=friend ──► set_friend_add_request(approve=True)（沿用 auto_friend 逻辑）
notice friend_add   ──► 私聊发注册引导（社区简介 + 规则摘要 + "回复 /注册 完成注册"）
/注册（私聊）        ──► 已注册 → 提示；未注册 → user_accounts 插入 + 欢迎语（引导拉群："把我拉进你的群，等待审核通过后群内功能开放"）
/菜单（私聊，白名单内）──► 已在 T0.8 支持；未注册用户看到的菜单 = 社区简介变体（⚠️ 待定）
```

**配置配合**：社区 `bot.system_plugins` 含 `register`、不含 `auto_friend/welcome`（T1.7 模板落值）。

**测试**：`test/scripts/check_register_flow.py`（独立进程集成脚本）：好友请求自动通过（mock API 断言）、friend_add 发引导、/注册落库、重复注册幂等。

**commit**：`feat(注册): 好友自动通过与注册流程插件`

### T1.4 群审核 `M`

**目标**：处理 `request_type=group`（sub_type=add/invite）事件 → 审核队列 → 超管指令批准/拒绝 → 激活播种。

**改动**：新插件 `plugins/group_review/`（或并入 register 插件目录，⚠️ 待定归属；建议独立——职责不同）；**先查 `specs/onebot-protocol.md` 与上游 OneBot v11 文档核对 `set_group_add_request` 参数（flag + sub_type + approve）**。

**流程**：

```
request_type=group ──► 黑名单群直接 reject；超限（community.max_groups / iter_active_groups 计数）直接 reject + 私聊告知邀请人
                    └─► group_requests 入队（存 flag/sub_type）+ 私聊通知全部超管：
                        "入群申请：群 {group_id}（名称经 get_group_info 解析，失败显示群号）· 邀请人 {user_id}\n/审核 {group_id} 通过|拒绝"
/待审（超管，私聊）──► 列出 pending 队列
/审核 <群号> <通过|拒绝>（超管，私聊）──► set_group_add_request(flag, sub_type, approve)
        通过 ──► group_registry 激活 + 播种默认功能包（打卡基础+经济扩展，复用 group_manager 的 _set_pack_config 逻辑——抽公共函数）
                 + 群内欢迎公告（⚠️ 文案待定）
        拒绝 ──► 标记 rejected + 私聊回执邀请人（best-effort）
notice group_increase（bot 自身入群）──► 若群不在 registry（如超管手动拉入）→ 入队并通知超管补审（不自动激活，门控挡着）
notice group_decrease（bot 被移出/退群）──► group_registry.status=removed（保留审核记录，防重复入队通知刷屏——同群再邀请重新走审核）
```

**测试**：`test/scripts/check_group_review.py`：入队→通知→通过→激活+播种→群事件放行；拒绝路径；超限路径；bot 被移出后群事件再次被门控拦截。

**commit**：`feat(审核): 拉群审核队列与超管批准流程`

### T1.5 拉黑与指令频控 `M`

**目标**：反滥用最小集。

**改动**：`core/base.py`（频控）+ 复用 T1.1 blacklist 表 + 新超管指令（建议挂 `plugins/group_manager/` 或 register 插件，⚠️ 待定归属——建议 group_manager，它已是管理指令聚集地）。

**频控设计**（中央一处，全部 CommandPlugin 自动受益）：
- `CommandPlugin.match` 尾部（命令已匹配后）：`uid = user_id`，键 `(uid, cmd)`，距上次执行 < `community.cmd_cooldown_seconds`（私有 edition 缺省 0 = 关闭）→ `return False` 静默忽略；内存 dict + 类级锁，重启清零（`# ponytail: 内存频控，重启清零；需持久化时落表`）。只读检查，不违反"match 无副作用"。
- 自定义 match 的插件（activity/who_is_spy 等）批次 2 各自补（任务里列出）。

**拉黑指令**：`/拉黑 用户|群 <id> [原因]`、`/解除 用户|群 <id>`（超管，写 blacklist；门控 T1.2 生效）。菜单文本同步。

**测试**：`test/test_cooldown.py`（同用户同指令冷却内二次 match 为 False、不同用户互不影响）；拉黑指令读写 + 门控联动（T1.2 已有，补指令路径）。

**commit**：`feat(风控): 指令频控与黑名单指令`

### T1.6 管理权限收紧 `S`

**目标**：管理/配置操作全部仅限 config 设定的超级用户——群主自治不开放（2026-09-08 所有者决策，总计划 D11，原待定项已否决）。

**改动**：
- `plugins/grant_points_all`：`admin_user()` → `super_user()`（仅社区 edition；私有版保持 admin_user，用 `config.EDITION` 分支——权限点属允许的 edition 接缝）。该项已在总计划 §8-3 落定。
- `plugins/group_manager` 的 `/插件` `/功能包`：**两形态均维持现状仅超管**，不做任何群自治开放；跨群操作沿用现有 `[群号]` 参数语法，超管无需进群即可远程开关任意群的功能包。
- T1.4 审核播种后的包调整：超管经 `/功能包 <名> [off|关闭] <群号>` 操作（既有能力，零新增代码）。

**测试**：`test/test_group_manager_perms.py`（新）：两形态下群管理员使用 /插件、/功能包 均被拒；超管跨群开关生效；grant_points_all 社区版群管理员被拒、私有版群管理员放行。

**commit**：`feat(管理): 社区版管理权限收紧为仅超级用户`

### T1.7 社区配置模板 `S`

**产出**：`config.example.community.yaml`（完整可用模板）：
- `bot.edition: community`、新 QQ 号占位、`super_users`、WS 连接
- `bot.system_plugins: [menu, group_manager, backup, update, register, group_review, monitor]`（无 message_logger/startup_changelog/auto_friend/welcome）
- 无 `timeline`/`onebot`/`webapp`/`live`/`weekly` 节（或留空）
- `community: {max_groups: 50, cmd_cooldown_seconds: 3}`

**同步**：`docs/community/` 增补部署小节（bot 单进程 systemd unit 参照 `docs/web-apps-deployment.md` 裁剪）；部署按 **git tag 固化**（本任务打出首个社区部署 tag，如 `community-v1`，后续升级 = 显式 bump tag）。

**验收**：`BOTERO_CONFIG=config.example.community.yaml python -c "import main"` 级别的干跑不退出（实际为 `import core.config` 成功）+ 插件全部注册。

**commit**：`feat(社区): 社区版配置模板与部署说明`

### T1.8 跨群一致性测试（W2 落地）`S`

**目标**：以测试固化"用户全局账户"语义。

**内容**：`test/test_cross_group_identity.py`：同一 user_id 在群 A、群 B、私聊三个上下文各执行打卡/抽卡 → 断言：钱包余额唯一变化、`count_days`/周常进度单份、称号单套；同日多群打卡 = 同日多次打卡语义（第二条记录存在、连续天数不变）。

**commit**：`test(社区): 跨群私聊全局账户一致性断言`

---

## 4. M2 · 上线装配

### T2.1 私有部署全量回归 `S`

pytest 全量 + 手工冒烟清单（打卡/补卡/撤回/抽卡/商店/称号装备/周常/排行/闹钟/活动/网页打卡/论坛）逐项过；任何回归回到对应任务修复，不带病上线。

### T2.2 社区实例部署与试运行 `M`

新 QQ 号 + NapCat 容器接入（复用现有部署方案）；`config.yaml`（社区模板落值）；systemd 单 unit；工作目录 checkout 固定 tag（T1.7 打出，升级时显式 bump）；**先拉自有试运行群跑 1-2 周**（运营建议：注册分时段放量，防新号风控）。观察项：好友请求频次、审核队列时延、频控误伤。

### T2.3 批次 1 正式验收 `S`

按 community-edition-plan §4 批次 1 验收逐条执行并记录：冷启动全链路（加好友→注册→私聊打卡→拉群→审核→群内全流程）、跨群+私聊唯一账户、私有部署回归。

### T2.4 运营物料 `S`（⚠️ 内容全部待所有者定稿）

注册引导文案、社区规则摘要（含 AI 作品政策占位——总计划 §8-4）、群欢迎公告、社区版菜单文案终稿、（可选）推广说明。仅改 `plugins/register/`、`bot_menu_text.py` 常量与配置。

---

## 5. M3+ · 批次 2/3 粗粒度任务（上线后按同格式细化）

| 任务 | 内容 | 已知前置工作 |
|---|---|---|
| B2.1 娱乐工具包释出 | dice/divination/random_reference/group_alarm 群审核通过后可开；group_alarm 已带 group_id，审计私聊闹钟（group_id=0）在多群服务的语义 | T0.9 审计结论 |
| B2.2 活动包释出 | activity 指令 + 网页接力提交的 bot 侧心跳（activity_timer）多群并发审计（按 activity.group_id 遍历，现结构已支持，需回归） | T0.9；`/活动` 群内创建固定 `DEFAULT_GROUP_ID` 处改为 `bot_event.group_id`（grep 确认改造点） |
| B2.3 卧底释出 | who_is_spy；`context.game_rooms` 已按群 keyed，补多群并发回归；跨群统计全局（D4 口径） | — |
| B2.4 群管理工具释出 | group_essence/set_group_title/recall_message 默认关、群主可开；需 bot 群管理员身份的使用提示 | T1.6 权限模式 |
| B3.1 跑团包释出 | trpg 三插件；`core/context.py` 录制状态（recording_sessions/group_roles/GAME_SYSTEM）迁入 `plugins/trpg_session`，`core/api.py` 录制钩子的 `is_group_recording` 调用改经注册式 hook（复用 T0.6 模式） | T0.6 模式 |
| B3.2 周报社区化评估 | weekly_report 数据源站内化（去 message_logger 依赖）后评估是否进社区包；不进则永久私有 | 市场计划 4.1 |

## 6. 明确不做（防执行时顺手扩散）

- 不拆仓库/不建包管理结构（D5 同代码库）；
- 不动 web 侧任何表与模块（批次 1 不带 webapp）；
- 不引入账号密码/网页注册/多平台适配（D2/D3）；
- 不做内容审核系统（举报/机审/处置流）——后置到 web 社区化阶段；
- 不动 `immortal_lottery`/`ff_news`/`message_logger`/`weekly_report` 本体（社区直接不启用）。

---

## 7. 执行纪律

1. 严格按依赖顺序；同里程碑内无依赖任务可任意穿插。
2. **每个任务动工前 spec 与 plan 两份文档必须齐全**（spec → `docs/superpowers/specs/YYYY-MM-DD-<名>-design.md`，plan → `docs/superpowers/plans/YYYY-MM-DD-<名>.md`，均在任务标题下挂引用链接）；S 级任务允许精简但不可缺；单点小修/纯文档除外（AGENTS.md §功能开发主流程）。缺任一文档不得写代码。
3. ⚠️ 标记项在动手前找所有者确认，确认结果回写本文档（划掉待定、记录结论）。
4. 每完成一个任务：勾选对应复选框（见下）、跑全量 pytest、按约定 commit。

**进度追踪**：

- [ ] M0：T0.1 T0.2 T0.3 T0.4 T0.5 T0.6 T0.7 T0.8 T0.9
- [ ] M1：T1.1 T1.2 T1.3 T1.4 T1.5 T1.6 T1.7 T1.8
- [ ] M2：T2.1 T2.2 T2.3 T2.4
- [ ] M3+：批次 2（B2.1-B2.4）· 批次 3（B3.1-B3.2）
