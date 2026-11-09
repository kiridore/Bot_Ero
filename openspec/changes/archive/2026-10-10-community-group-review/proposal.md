# 群审核：由超级用户逐群批准服务

## Why

一个公开QQ账号服务多个群，维护者需要决定哪些群可以接入，而不是收到邀请就自动服务。群开关负责已接入群的功能范围，群审核负责是否接入；两者不能相互代替。限制接入数量可以降低资源和维护负担。

## What Changes

- 新增group_review插件：群邀请进入待审清单，不自动同意；黑名单或容量不足时拒绝。只处理邀请机器人入群，不审批群成员的普通入群申请。
- QQ指令 `/待审`、`/审核 <群号> 通过|拒绝` 仅超级用户可用，建议私聊操作；本次不增加Web审核页面。
- 批准时确认OneBot成功、登记群为active并为该群开启配置指定的打卡基础包；失败不得宣称批准成功。欢迎公告暂用「本群已接入打卡服务，/菜单 查看可用功能」。
- 已被手动拉入的群也待审并提醒超级用户，不自动激活；移出机器人时标记removed，保留历史。
- 可选群审核要求：关闭时旧部署不受影响；开启时未激活群不能使用业务，包括属于该群的后台任务。生命周期通知和审核本身仍须能处理，不能被未激活检查挡住。
- 复用已交付group_registry/group_requests/blacklist数据层，但允许完善缺失接口与请求状态，不能把已有表等同于已实现业务。

## Capabilities

### New Capabilities
- `community-group-review`：邀请、手动入群、审核与容量控制。

### Modified Capabilities
- `community-access-registry`：独立请求编号、审批及远端结果状态、旧表原子迁移。
- `scoped-heartbeats`：启用审核时，群任务要求群已激活。

## Impact / Scope

涉及新插件、配置与校验、main/context群检查、OneBot接口、community数据事务、菜单文案包、公开模板和文档。必须先核对权威协议再编辑事件/API代码。纯同步；部署差异只来自配置。旧配置缺省关闭审核，不要求已有私有群补登记。

不包含注册改造、拉黑管理指令、全局指令冷却、自动审批、群管理员自行审批、Web审核、自动退群或数据删除。公开上线仍需协议定稿及运营试用验收。

## 验收标准

实现测试集中在test/test_group_review.py与test/test_group_review_data.py，避免为每条标准复制测试准备代码；下列命令按实际文件更新，验收条件保持不变。

| 标准 | 独立验证 | 通过条件 |
|---|---|---|
| AC01 | `python -m pytest test/test_group_review.py -k "invite or rejection or join or leave"` | 邀请去重、普通成员申请不处理；黑名单/容量拒绝；拒绝失败保留可处理记录；手动入群待审、通知超管；移出仅标记removed |
| AC02 | `python -m pytest test/test_group_review.py -k "approve or request or users or seed or manual"` | 仅超级用户能审批；非法目标/无待审/多凭证不误审；成功批准后激活与基础包同事务；拒绝不激活；重复指令不重复调用或公告 |
| AC03 | `python -m pytest test/test_group_review.py test/test_group_review_data.py -k "failure or unknown or remote or concurrent or rollback or manual or exception"` | API超时/失败不误标成功；成功API后DB失败可恢复且不盲目重发；并发审批不超过容量；手动已入群不调用无凭证的邀请审批接口 |
| AC04 | `python -m pytest test/test_group_review.py test/test_scoped_heartbeats.py -k "scope or main_loop or alarm or backup or heartbeat or group_messages"` | 未激活群不运行普通业务或群后台写入，生命周期仍可处理；A群激活不开放B群；群状态读取失败限制业务；私聊及共享任务不被误挡 |
| AC05 | `python -m pytest test/test_group_review.py test/test_deployment_templates.py -k "configuration or edition or template or scope"` | 缺省关闭兼容旧配置；同配置不同edition一致；启用时插件/系统集合/默认包有效；播种不越过部署许可；容量及配置类型校验 |
| AC06 | `python -m pytest` | 全量隔离测试通过，不触真实数据；菜单、schema变动及对应知识库、配置、CHANGELOG和minor版本同步 |
| AC07 | `openspec validate community-group-review --strict` | 严格校验和临时副本归档合并检查通过，验收记录逐条有证据，全部通过后才正式归档 |

## 维护者可持续性影响

以待审列表和明确失败状态减少翻日志处理；无自动审批/反复重试产生的维护负担。容量由配置控制。验收须演练一次批准、拒绝及故障恢复，确认维护者能仅凭QQ回执定位下一步；不承诺零人工审核或无条件私聊可达。
