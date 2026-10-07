# 提案验收核查（草稿 PR）

## 结论

**尚未完成所有开发任务，整体验收不通过，禁止归档或作为已完成版本合并。**

当前 tasks.md 为14/19。全部现有测试通过不等于已经实现全部要求。实际代码仍保留抽奖对周常/称号的直接调用，以及抽奖、周常、称号、商店的旧消息发送入口；BOTERO_VERSION 仍为1.50.0，尚未准备本次功能发布版本。

## 本次重新执行的验证

| 标准 | 执行命令（均以 python -m pytest 开头） | 测试结果 | 核查判断 |
|---|---|---|---|
| AC01 | test/test_plugin_dispatch.py -k thread -q | 2 passed | 当前线程及事件隔离测试通过 |
| AC02 | test/test_plugin_controls.py test/test_plugin_management.py test/test_web_panel.py -q | 35 passed | 账号/群设置、权限、兼容和系统保护通过 |
| AC03 | test/test_plugin_event_integration.py -k disable -q | 5 passed | 打卡相关路径通过；抽奖未迁移，不能视为全部插件关闭语义已完成 |
| AC04 | test/test_plugin_output.py test/test_plugin_send_compatibility.py -q | 16 passed | 输出基础和已迁移入口通过；未迁移入口仍需5.4处理 |
| AC05 | test/test_plugin_dispatch.py -k failure -q | 2 passed | 通知处理失败隔离通过 |
| AC06 | test/test_reward_records.py -q | 9 passed | 奖励事务、并发和重复处理基础通过；抽奖集成仍需5.3验证 |
| AC07 | test/test_reward_compatibility.py -q | 8 passed | 已接入奖励的新旧兼容与撤销通过 |
| AC08 | test/test_plugin_event_integration.py -q | 11 passed | 打卡/撤回通过；缺少迁移后的单抽/一键抽奖及全部入口对照，完整要求未通过 |
| AC09 | test/test_plugin_migration_inventory.py test/test_plugin_migration_baseline.py -q | 10 passed | 清单与规则对照通过；迁移未全完成、版本尚未递增，交付要求未通过 |
| AC10 | -q（全量） | 499 passed，11275 warnings，322.95秒 | 全量回归通过，告警主要为已有Python/pytest_asyncio弃用项；不替代其他验收项 |

另执行 `openspec validate plugin-event-dispatch --strict` 通过；`git -c core.whitespace=cr-at-eol diff --check` 通过。完整命令日志保存在本地 `.git/plugin-event-dispatch-acceptance/`，不上传测试运行日志或凭证。

## 未完成任务与源代码证据

- **5.3**：plugins/lottery/__init__.py 仍导入并调用 on_quest_trigger / evaluate_and_unlock_titles；单抽与一键抽奖仍调用 api.send_msg / api.send_forward_nodes。
- **5.4**：plugins/weekly_quest/__init__.py、plugins/title/__init__.py、plugins/redeem_shop/__init__.py 的命令和定时输出仍直接调用发送API。
- **6.1**：本次已完成核查与可执行测试，但不能勾选“全部AC01–AC10通过”；缺失实现仍需补齐后重新验收。
- **6.2**：需要在开发完成后递增minor版本、准备对应CHANGELOG节并完成发布文档检查。
- **6.3**：全部验收通过后才归档。本次提交草稿PR不归档、不合并master、不表示已交付。

## PR 范围

开发分支 feature/plugin-event-dispatch。包含同步通知/输出基础、账号开关、已迁移的打卡及撤回流程、奖励事务与兼容、测试和提案。community-feature-packs 为明确暂停的历史草案，不是当前实施依据。

本 PR 仅用于保存进度和审阅；私有部署会直接更新master，因此不得将未完成重构作为可发布代码合并。所有者仅授权本次重构的插件独立开关及消息合并语义变化，不扩大社区首版功能范围。
