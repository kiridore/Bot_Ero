# 插件同步通知、独立开关与统一消息输出

## Why

打卡、抽奖目前直接调用周常、称号和商店逻辑，关闭被调用插件并不能停止这些联动。需要在保持单进程同步多线程的前提下，让插件通过内部通知协作，并统一收集、合并输出消息。

## What Changes

- 每个外部事件仍创建一个线程；内部通知、插件处理及最终消息发送都在该线程内完成。不同事件各自持有通知列表和输出列表，不增加后台线程、外部消息服务或 async。
- 第一阶段迁移打卡、两种撤回打卡、抽奖、周常、称号，以及打卡消费商店道具的处理。消除这些流程中直接调用其他插件业务处理函数的依赖。
- 必需的输出模块收集发送请求；仅同次操作、同一接收位置、相同非空合并标记的普通文本可合并，按显示顺序及提交顺序排列。无标记、图片和转发消息不强行拼接。
- 私聊增加逐账号设置：沿用公共默认、单独开启、单独关闭；群聊继续使用各群设置。只有超级用户可以修改，兼容现有管理指令。
- 操作开始时固定开关状态；关闭后停止新奖励，不自动补发关闭期间奖励。撤销已有奖励不受当前奖励插件开关限制；关闭操作本身不追溯历史奖励。
- 新奖励记录与积分变更同一事务提交；准确识别重复处理和重复撤销。旧奖励按现有规则处理，不猜测历史来源。
- 单个处理函数失败后继续其他独立处理；不接收失败函数尚未确认的通知及成功提示。保留已完成的打卡，记录错误并发送简短失败说明。不自动重试业务或发送结果不明的消息。
- **BREAKING（所有者明确许可，仅本次）**：私有版也采用真正独立的插件开关；已关闭插件不再通过其他插件产生新奖励。允许消息合并后的输出变化，但不借机改动奖励数值、称号撤销规则或社区开放范围。
- 所有者补充裁定：称号关闭时暂时禁止单抽和一键抽奖，必须在扣费、次数消耗和随机抽取前拒绝；抽卡消费查询不受影响，不修改称号奖项占比和返点规则。
- 后续必须迁移所有插件的消息发送；本提案交付第一阶段及完整后续迁移清单，不把其他插件已迁移作为本次承诺。

## Capabilities

### New Capabilities
- `plugin-event-processing`：同步通知、独立开关、奖励记录、失败隔离和消息输出契约。

### Modified Capabilities
- `system-plugins`：非系统插件的私聊开关增加账号覆盖；群聊设置及现有外部 meta 事件派发规则保持。本次账号设置不用于关闭必需系统组件。

## Impact

涉及 main.py、core/base.py、core/context.py、core/api.py、数据库管理与 schema、group_manager 和第一阶段插件；拟新增通知与输出模块、账号设置及奖励记录数据库操作。复用现有 SQLite，不新增运行服务。实现属于用户可见功能变化，必须增加 BOTERO_VERSION minor 版本及对应 CHANGELOG 节，不能援引旧提案“不 bump”的裁定。

旧 `community-feature-packs` 草案中关闭积分、按包名判断经济能力等方案已被本次讨论取代，不是实施依据。社区首版仍为打卡基础与积分系统开放、经济扩展关闭；不擅自增加周常和称号管理指令、不删除 dice 插件。

## 验收标准

以下命令中的新测试文件由本次实现交付；现阶段不声称已运行或已通过。

| 编号 | 独立验证命令 | 必须验证的结果 |
|---|---|---|
| AC01 | `python -m pytest test/test_plugin_dispatch.py -k thread` | 生产者、消费者和最终发送在同一事件线程；两个并发事件的通知和输出不混用；处理可继续产生通知直至本次完成 |
| AC02 | `python -m pytest test/test_plugin_controls.py test/test_plugin_management.py test/test_web_panel.py` | 群设置、私聊公共默认、账号三态覆盖、恢复默认、非超级用户拒绝、旧指令兼容、群号与账号明确区分、当前操作固定开关以及新操作看到新值 |
| AC03 | `python -m pytest test/test_plugin_event_integration.py test/test_lottery_events.py -k disable` | 分别关闭周常、称号、商店时，仅对应新业务停止；打卡和其他启用插件继续；私有和社区采用一致规则；重新开启不自动补发 |
| AC04 | `python -m pytest test/test_plugin_output.py test/test_plugin_send_compatibility.py` | 标记/接收方/操作边界、无标记单发、稳定显示顺序、换行、图片和转发独立、群私聊隔离、失败输出丢弃、发送失败不重跑业务不自动重发 |
| AC05 | `python -m pytest test/test_plugin_dispatch.py -k failure` | 一个处理函数失败不阻止其他独立函数；已保存打卡不丢失；失败函数未确认提示和子通知不发布；错误日志和用户提示存在且不泄露内部异常细节 |
| AC06 | `python -m pytest test/test_reward_records.py test/test_lottery_events.py` | 发奖/撤奖记录与积分原子提交；故障注入回滚；同一业务奖励重复通知、跨线程竞争只能发一次；同一撤销只能扣一次；撤销后合法重新达标可再次发奖 |
| AC07 | `python -m pytest test/test_reward_compatibility.py` | 关闭周常后仍能撤回旧奖励；未曾发奖不扣分；旧记录可撤销且与新记录不双扣；不收回已解锁称号，不改变累计周常完成和历史全清的现有规则 |
| AC08 | `python -m pytest test/test_plugin_event_integration.py test/test_lottery_events.py test/test_lottery_bulk.py test/test_plugin_command_output.py` | 打卡、消息撤回、指令撤回、单抽和一键抽奖完整流程；奖励插件全开时数值/记录与改造前一致，输出符合新合并规则；第一阶段发送均走统一模块 |
| AC09 | 审阅 `migration.md`；`git -c core.whitespace=cr-at-eol diff --check` | 所有 bot 插件直接/间接发送位置有逐文件清单，第一阶段范围与后续阶段明确；未迁移不标完成；相关 specs、kb、菜单和 CHANGELOG 更新，版本号一致 |
| AC10 | `python -m pytest`；`openspec validate plugin-event-dispatch --strict` | 全量回归与提案校验均通过；测试绝不触碰真实 data.db/server_data；旧私有配置可加载，schema 增量升级不丢数据 |

验收逐条全绿后才允许 `openspec archive plugin-event-dispatch`，归档与本阶段实现同一提交。所有者已授权实施。实现完成且验收全绿前不归档、不提交、不推送。工作树原文件已使用 CRLF；差异检查使用 cr-at-eol 识别既有行尾，不为消除误报而重写整文件。
