# 黑名单管理验收记录

## 范围与状态

版本1.56.0。QQ机器人及其后台任务实现完成；本记录不表示独立网页服务新增封禁认证，也不表示真实QQ联调已完成。旧配置缺省关闭新限制，已有群审核保护保留。

## AC01–AC09证据

执行 `python -m pytest test/test_blacklist*.py test/test_community_db.py test/test_deployment_templates.py -q`：90 passed。

| 标准 | 测试证据与结果 |
|---|---|
| AC01 | test_blacklist_management：真实main管理指令，增删查、重复、分页、原因/操作者、无权限及失败不报成功；通过 |
| AC02 | management/protection及lifecycle：当前超管/机器人保护，历史行保留，被封群不能超管绕过，私聊可管理；通过 |
| AC03 | entry/recovery：跨群私聊、独立群限制、静默和额度、代补卡目标、私聊活动/房间真实所属群；通过 |
| AC04 | concurrency/foundation：线程屏障、等待者不得用旧快照、锁不跨业务等待；旧指令及通知完成，新提交拒绝。tasks/activity_game验证逐条任务及同活动多阶段快照；通过 |
| AC05 | tasks/bulk_points/activity_game/notifications：暂停记录、正常群结算、免费称号排除、正负积分过滤、整批回滚、私聊过滤、共享维护和定向公告区分；通过 |
| AC06 | cleanup：真实数据库撤回旧奖励、重复不多扣、无新奖励或回复、部署禁止仍生效；通过 |
| AC07 | lifecycle：好友/群邀请、成功失败未知、重复事件、欢迎抑制、机器人进退群、读取失败只维护事实；通过 |
| AC08 | recovery/tasks：解除不注册、不激活、不改插件设置；已有任务按原规则恢复，读失败保留记录；通过 |
| AC09 | config/foundation/community_db/deployment_templates：类型校验、缺省关闭、版名无差异、公开配置启用、旧表迁移保留和失败回滚；通过 |

## AC10交付验证

- 调用清单：call-inventory.md；协议单页核查：protocol-check.md；私聊发送文件遗漏检测：test_blacklist_call_inventory.py。
- 操作手册：docs/community/blacklist-operations.md。菜单、模板、数据库、插件规范、知识库、开发清单、版本及CHANGELOG已同步。
- 全量 `python -m pytest -q`：779 passed。告警为pytest-asyncio的弃用提示，未屏蔽告警。
- 变更严格校验通过。临时副本首次归档因工具生成Purpose占位导致规范严格校验失败；已给新增能力补正式Purpose，再次副本归档后15个规范严格校验全绿。副本中的第4.2项保留未勾选，因为真实归档和提交尚未发生；没有把模拟归档当成真实交付。
- 正式归档目录：2026-10-20-blacklist-management；最终正式规范校验与提交完成后记录于progress.md。

## 保留限制与上线检查

- 未进行真实QQ联调；必须使用测试账号/群核验申请拒绝、静默、定时恢复和管理员私聊操作。
- 已获准完成是“不因后续封禁中断”，不是对所有业务及外部API的分布式事务承诺；网络未知结果不伪报成功。
- 错过原开奖窗口的付费注单不新增自动补偿或补开奖，保留供人工核查。
- 新限额与封禁均按单实例执行；直接外部改库不参与应用内锁协议。
- 全套测试由conftest和临时数据库隔离；真实QQAPI使用替身，活动归档及游戏记录输出不写真实server_data。
- 维护者可持续性：不引入新服务、轮询重试队列或到期解封任务；人工故障处理边界已在手册注明。
