# 第一阶段最终验收

## 结论

第一阶段实现及AC01–AC10均通过本次核查，版本1.51.0。只覆盖本提案明确的首批插件；所有其他插件发送迁移及部署配置统一化仍属后续工作，不能称为全项目迁移完成。

最终验收补齐商店称号商品的依赖检查：称号关闭时在扣费/扣库存前拒绝，其他商品仍可兑换。私有与社区共用同一规则，无新增edition业务分支。

## 实际执行结果

命令均以 `python -m pytest` 开头，末尾 `-q`。完整本地日志在 `.git/plugin-event-dispatch-final/`，不上传凭证和运行日志。

| 标准 | 测试路径/选择条件 | 结果及审查 |
|---|---|---|
| AC01 | test/test_plugin_dispatch.py -k thread | 2 passed；同事件线程、并发事件隔离与主入口快照 |
| AC02 | test/test_plugin_controls.py test/test_plugin_management.py test/test_web_panel.py | 35 passed；账号覆盖、默认继承、旧指令、包批量事务、权限与系统保护 |
| AC03 | test/test_plugin_event_integration.py test/test_lottery_events.py test/test_plugin_command_output.py | 42 passed；打卡/抽奖开关、群与私聊、相同配置的两版标签行为一致，商店称号关闭不写库 |
| AC04 | test/test_plugin_output.py test/test_plugin_send_compatibility.py | 18 passed；合并边界、节点分组、稳定顺序、特殊消息、长度、发送失败不重跑业务 |
| AC05 | test/test_plugin_dispatch.py -k failure | 3 passed；单个消费者失败隔离、丢弃未确认输出和通知、有限循环保护；额外集成测试覆盖错误提示不泄密 |
| AC06 | test/test_reward_records.py test/test_lottery_events.py | 22 passed；原子性、故障回滚、并发/重复来源与次数上限、合法重新领取 |
| AC07 | test/test_reward_compatibility.py | 8 passed；新旧领取和反复撤销、余额不足、旧撤回不影响后来领取；集成测试另覆盖关闭后撤销及周/月边界 |
| AC08 | test/test_plugin_event_integration.py test/test_lottery_events.py test/test_lottery_bulk.py test/test_plugin_command_output.py | 50 passed；真实首批插件与单抽/一键结果，迁移文件禁止旧发送入口 |
| AC09 | test/test_plugin_migration_inventory.py test/test_plugin_migration_baseline.py | 10 passed；发送文件清单和固定奖励/价格对照；版本1.51.0与CHANGELOG一致，菜单、schema、玩法、架构与社区前置计划同步 |
| AC10 | 全量pytest | **533 passed，14466 warnings，315.08秒**；告警主要为现有Python/pytest_asyncio弃用项；测试使用隔离配置和数据库 |

归档后再次全量回归：533 passed，14466 warnings，321.21秒。清单测试已验证能从归档目录读取迁移记录。

全项目OpenSpec严格校验最初发现system-plugins/text-packs/timeline-reporting三份历史规范的Purpose仍为自动生成占位文字，已补充用途说明（不改变行为契约）；重新执行 `openspec validate --all --strict`：5 passed、0 failed。Git CRLF兼容差异检查、文档链接与版本一致性通过。旧私有配置的加载沿用既有回归测试，不加载或修改生产数据。

## 合并与后续边界

- 在feature/plugin-event-dispatch提交交付修复、版本说明和提案归档，不能把开发过程中的未完成快照当作独立发布点。
- 不自行合并master；私有部署会直接拉取master，需所有者决定合并与上线。
- 后续插件名单及发送路径以migration.md为准；卧底游戏、其他普通命令、系统任务等未因此阶段归档而视为已迁移。
- core/config.py既有按edition校验与默认值差异仍按docs/community/config-only-plan-review.md另行统一，本次未新增该类分支。
