# 社区版开发与完成清单

> 按当前1.56.0代码与归档核对，替代旧1.37.2任务步骤；只列有效方案，不保留旧代码片段。范围以[当前需求](community-edition-plan.md)为准。最近实现回归：779 passed（黑名单管理验收时），不等于真实QQ或公开上线验收。

## 1. 总体状态

- [x] M0：T0.1–T0.9的目标已由现有配置化和通知改造实现，不再开发另一套功能包/菜单。
- [ ] M1：注册、群审核、权限和模板主体已交付；注册入口与欢迎模板已修复，每账号指令总次数限制已完成。黑名单管理已交付；剩余升级方式、补卡权限和跨对象上线验收。
- [ ] M2：真实QQ联调按所有者要求暂缓，不阻塞当前开发；没有完整的公开实例试运行及上线验收证据，不能标完成。
- [ ] M3+：候选功能按反馈选择，不预先承诺全部开放。

## 2. 已完成项：需求、现状与证据

| 编号 | 当前交付 | 对应需求及设计原因 | 证据 |
|---|---|---|---|
| T0.1 | 配置统一校验，edition仅描述，缺省一致 | 同样配置同样行为，不维护两套加载逻辑 | [config-unification](../../openspec/changes/archive/2026-10-08-config-unification/acceptance.md)、core/config.py |
| T0.2 | 无接收群且无默认群时丢弃群发 | 公开实例不能误向某个私域群发送 | test/test_api_send_fallback.py |
| T0.3 | 时间线上报空配置关闭 | 首版纯bot不依赖webapp | [timeline-report-noop](../../openspec/changes/archive/2026-10-06-timeline-report-noop/proposal.md) |
| T0.4 | 系统插件集合配置化，部署名单仍为上限 | 必要管理能力可配置，不能绕过部署禁止 | [system-plugins规范](../../openspec/specs/system-plugins/spec.md) |
| T0.5 | 周常引擎移至插件目录 | 玩法不反向嵌入公共工具 | [quest-engine-extraction](../../openspec/changes/archive/2026-10-06-quest-engine-extraction/proposal.md) |
| T0.6 | 称号前缀通过注册提供者接入 | core不直接依赖称号插件 | [title-prefix-hook](../../openspec/changes/archive/2026-10-06-title-prefix-hook/proposal.md) |
| T0.7 | 功能包文件、部署允许名单、按群/账号开关 | 功能包仅批量设置；新增代码不自动开放 | core/feature_packs.py、feature_packs_public.yaml、config-unification |
| T0.8 | 结构化有效菜单和逐条文案包 | 同功能同规则，文字可按配置替换 | [enabled-menu](../../openspec/specs/enabled-menu/spec.md)、[text-packs](../../openspec/specs/text-packs/spec.md) |
| T0.9 | 心跳部署限制及按任务所属对象检查 | 不允许关闭后仍推进群/账号任务 | [scoped-heartbeats](../../openspec/specs/scoped-heartbeats/spec.md)、test/test_scoped_heartbeats.py |
| T1.1 | 账号、群登记、申请、黑名单存储；申请独立编号与迁移 | 运营状态可恢复，不将存表误作业务已完成 | [community-access-registry](../../openspec/specs/community-access-registry/spec.md)、test/test_community_db.py、test/test_group_review_data.py |
| T1.3 主体 | 主动注册、协议同意、账号基础包与资料卡 | 同意后才登记，按账号逐步开放 | [community-registration](../../openspec/changes/archive/2026-10-10-community-registration/proposal.md)、test/test_register_flow.py；入口与欢迎修复见下方R1/R2 |
| T1.4 | QQ超管审核、容量预留、远端/本地恢复、群业务限制 | 控制接入规模，失败不盲目重复批准 | [群审核验收](../../openspec/changes/archive/2026-10-10-community-group-review/acceptance.md)、[操作手册](group-review-operations.md) |
| T1.6 | 插件管理/账号设置/审核/批量发积分仅超管 | 群管理者不能修改全实例或其他对象 | test/test_plugin_management.py、[grant-points-superuser](../../openspec/changes/archive/2026-10-10-grant-points-superuser/proposal.md)；不代表所有玩法权限均已公开化审核 |
| T1.7 主体 | config.public.example.yaml、基础包文件及操作手册 | 可用同一程序装配公开实例 | test/test_deployment_templates.py；欢迎已补齐，已有实例须同步配置，固定版本升级仍见R3 |
| R1/R2（1.54.2） | 未注册菜单使用实际menu标识，好友请求不再被注册检查误拦；公开模板启用welcome，申请同意、欢迎、主动注册各司其职 | 新用户能收到引导并查看菜单，不提前开放业务；修复真实事件入口而非仅测试菜单函数 | [注册入口验收](../../openspec/changes/archive/2026-10-18-registration-entry-fixes/acceptance.md)、test/test_registration_entry.py；已有实例按[操作说明](registration-entry-operations.md)补齐配置，真实送达仍待M2 |
| T1.5 指令总次数限制（1.55.0） | 同账号跨群/私聊滚动60秒最多20次；超管同样受限；匹配后一次计数、超限不执行业务、提示每10秒至多一次，重启清空 | 防止高频调用影响其他用户；既有配置缺省0关闭以保持兼容，公开模板填20，不增加数据库负担 | [限额验收](../../openspec/changes/archive/2026-10-19-command-rate-limit/acceptance.md)、[配置说明](command-rate-limit.md)；全量708 passed，本地提交17d5e20 |
| 查询修复 | 私聊列表查本人，明确查询公共默认，显示有效状态及来源 | 避免注册后误查公共默认，保留原修改语义 | [plugin-query-scope](../../openspec/changes/archive/2026-10-13-plugin-query-scope/acceptance.md)，1.54.1 |
| 通知迁移第一阶段 | 打卡、撤回、抽奖、周常、称号、商店相关通知/输出与奖励事务 | 独立开关不再依赖直接调用，失败不产生部分积分记录 | [plugin-event-dispatch](../../openspec/changes/archive/2026-10-07-plugin-event-dispatch/acceptance.md)，1.51.0；并非所有插件发送入口均已迁移 |

黑名单交付（T1.5，1.56.0）：按对象停止新业务而不没收历史或已承诺付费权益，避免滥用影响其他对象；证据见[验收记录](../../openspec/changes/archive/2026-10-20-blacklist-management/acceptance.md)和[操作手册](blacklist-operations.md)。真实QQ联调按所有者要求暂缓，不计为验收通过。

T1.2不是一个还要重做的“总开关”：部署许可、账号设置、注册要求、群审核已经分别交付；T1.5的指令总次数限制已完成，黑名单限制和QQ管理入口也已交付（1.56.0）。T1.8仍需要明确的跨群/私聊验收记录，不能只凭共享账号表推断完成。

## 3. M1 剩余任务（先确认设计，再写相应提案）

| 编号与状态 | 做什么 | 所服务的要求与原因 | 完成条件 |
|---|---|---|---|
| R3 待方案确认 | 固定版本部署与现有/更新拉主干的冲突 | 公开服务需要可控升级，不能因管理员操作越过已验收版本 | 确认统一配置控制或公开部署禁用更新插件并使用运维升级；验证版本固定、备份及恢复。未经确认不改变私有更新行为 |
| R4 待权限确认 | remedy_checkin仍使用admin_user限制管理补卡，核对公开群管理员免费/代他人补卡规则；核查扣费与额度一致性 | 首版包含补卡，不能把插件管理仅超管误认为所有补卡权限也已收紧 | 所有者明确权限，随后按统一规则验收普通用户/群管理员/超管与并发扣费、失败回滚；不得按版名分支 |
| T1.8 待完整验收 | 首版账号跨A群/B群/私聊的数据与权限矩阵 | 一个账号共享积分和打卡，群与私聊开关却互不影响；真实组合需验证 | 同账号多入口数据一致、不同账号隔离、A开B关、账号覆盖和注册/审核限制；旧配置兼容、仅改edition无行为差异。已有测试复用，缺的再补 |

T1.5边界：指令总次数的配置、提示间隔、超管不豁免和内存存储已经定稿并交付，不再列为待决。旧`community.cmd_cooldown_seconds`仍未实施，与总次数限制是两回事；是否还需要同指令冷却须另行确认，不能默认追加为本轮上线前任务。黑名单已确认并交付：超管QQ管理、账号跨群/私聊限制、群独立限制、已获准操作完成，旧配置默认关闭。统一执行控制、match不新增状态写入、无edition业务分支的约束保持。

当前执行顺序：R3固定版本升级方案确认 → R4补卡权限与事务规则确认 → T1.8跨群/私聊自动化验收。真实QQ联调暂缓，不作为这些任务的前置条件；已有测试复用，缺少的组合测试在隔离环境补齐。

恢复真实QQ联调的时间由所有者另行确认。暂缓不等于免除正式上线验收，也不据此认定已可对外开放；进入公开试运行或正式开放前，重新确认实际部署验收安排及未验证风险。

部署提醒：代码及公开模板已更新，不代表已有实例配置已生效。升级时核对welcome名单、`community.command_limit_per_minute: 20`及`blacklist.enabled: true`，将blacklist加入部署允许名单和系统集合后重启；旧配置缺省限额为0、黑名单全局限制为false。详见[黑名单操作手册](blacklist-operations.md)。

## 4. M2 上线清单（真实QQ联调暂缓，均未取得完整完成证据）

当前可继续做配置、运维方案和运营材料的离线核对。T2.1中的实际QQ交互、T2.2真实QQ试运行、T2.3真实消息流程均暂缓；这些部分保留未完成状态，不用模拟响应或pytest通过替代。

| 编号 | 工作与验收 | 所服务的要求与设计原因 |
|---|---|---|
| T2.1 私有部署回归 | 同一待上线版本全量pytest；私有实际配置启动与关键玩法/网页交互冒烟；不将/更新执行成功视为全部回归通过 | 私有服务持续可用，代码测试无法替代真实外部服务验证 |
| T2.2 公开实例试运行 | 独立QQ号、DB及媒体目录；明确QQ后端/进程守护/固定版本升级；备份恢复和异常通知实际演练；先小范围群及账号 | 限制事故影响，确认真实接口、消息送达及恢复能力 |
| T2.3 首版验收 | 好友→欢迎→主动注册→协议同意→私聊功能；邀请/手动进群→审批→群内功能；拒绝/离群/超时恢复；同账号跨群与私聊合计20次后拒绝、提示位置与间隔、等待后恢复；跨对象权限与黑名单。每项留结果 | 模拟OneBot响应不证明实际QQ可用，也不代表可对外放号 |
| T2.4 运营材料核对 | 所有者已修改协议及注册文案，不重新要求从零起草；核对部署加载的文件、菜单实际开放范围、群公告、服务预期与隐私说明，再请所有者确认发布版本 | 防止代码行为与用户承诺不一致；资料定稿与技术上线是不同验收 |

每批上线必须记录“维护者可持续性影响”：新增人工流程、监控盲区、可自动化部分及故障处置步骤。参见[守则](sustainability.md)，不能为补齐候选自动化功能无限扩大首版。

## 5. 上线后候选，不是默认排期

- 后续插件统一输出迁移：所有插件最终用同一方式发送，避免长期维护两套；复用迁移清单，不声称第一阶段已覆盖全部。
- 娱乐、闹钟、活动、卧底、群管理工具、跑团：由运营反馈选定，每项重新核对依赖、数据归属、权限、心跳和多群并发；仍由超管开放，不授权群主自行开包。
- 经济扩展：首版之外，需明确批准和独立提案；不能因为代码已改造就自动添加到模板。
- 健康摘要、告警、反馈、数据导出和只读模式：可持续性候选；对外发送目的地、数据导出范围另行确认。
- 公开版每季度至多一次功能更新；其余时间修复问题。webapp与其他平台不在首版范围，不承诺后续必须上线。

## 6. 执行纪律

1. 每项新行为说明服务哪条需求及原因，未确认的选择先问所有者。
2. 要bump版本就先OpenSpec提案；完整验收后归档，实现/测试/规格/菜单/CHANGELOG同一逻辑提交。纯文档整理无需提案或版本更新。
3. 同一程序只由实际配置控制，不使用edition业务分支；关闭注册/审核要求应兼容旧配置。
4. 测试配置、DB和媒体都必须临时隔离；仅临时BOTERO_CONFIG不足以保证安全。模板子进程必须检查派生数据路径。
5. 未完成、不确定和缺少真实部署证据的项目不得勾选完成。代码测试、真实QQ试运行和正式开放分别验收。
