# 当前实施进度

## 已实现并验证

- core/plugin_dispatch.py：当前事件线程同步分发、开关快照、订阅所属插件、消费者数据副本、循环检测、失败时丢弃未确认通知与输出。
- core/message_output.py：明确接收方、按标记合并普通文本、稳定排序、特殊消息独立、文本分段不丢字符、发送失败不重试；复用 ApiWrapper 作为真实发送入口。
- main.py/core/base.py/core/context.py 已接入事件级处理对象与账号开关读取；未迁移插件仍用原发送方式。
- 私聊账号覆盖表及读写方法；group_manager 支持显式群/用户目标和账号恢复默认，修改入口检查超级用户身份；指令与文档同步任务尚未全部结束。
- plugin_reward_records 表、有效奖励与原操作唯一约束、同事务发奖/撤销基础服务；真实玩法尚未接入，旧记录兼容尚未交付。
- 称号关闭时拒绝单抽/一键抽奖，保持抽卡消费查询；群与私聊均有不产生数据库写入的测试。
- specs/architecture.md 纠正旧文档“每个插件一个线程”的错误，说明实际每事件一个线程。

## 验证记录

`python -m pytest -q`：432 passed，4440 warnings，319.96 秒。告警主要为现有 pytest_asyncio/Python 弃用告警。

重点新增测试：test_plugin_dispatch.py、test_plugin_output.py、test_plugin_controls.py、test_reward_records.py，以及 test_lottery_bulk.py 的称号关闭断言。

这是当前基础模块与原有回归的结果，不代表 AC01–AC10 已全部完成。待交付的 test_plugin_event_integration.py 和 test_reward_compatibility.py 不能视为已通过。

## 尚未完成

- 第一阶段真实业务生产者/订阅者迁移：打卡、撤回、抽奖、周常、称号、商店。
- 新奖励记录接管实际领取状态、旧奖励兼容、历史撤销防双扣的完整集成。
- 第一阶段所有发送入口迁移及完整集成对照测试。
- 管理指令剩余边界测试、菜单/知识库全面同步。
- minor 版本递增、CHANGELOG、逐条验收、提案归档及最终提交。

所有者要求保存并推送当前改动：以独立开发分支 `feature/plugin-event-dispatch` 保存未完成快照，不进入 master、不作为发布版本、不归档。全量回归再次运行：432 passed（316.75 秒）。所有未完成项保持 tasks.md 未勾选；后续完成菜单/版本/CHANGELOG 等交付要求并逐条验收后才能合并主干。本次可见行为变化得到所有者授权，但不扩大社区首版功能范围。
