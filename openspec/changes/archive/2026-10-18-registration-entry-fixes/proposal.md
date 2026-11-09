# 修复未注册菜单入口和公开欢迎配置

## Why

已确认两个接入缺口：

1. core/context.py的REGISTRATION_ALLOWLIST使用show_menu，但调度器plugin_key按模块目录得到menu。MenuPlugin.name虽为show_menu，并不是调度标识；直接调用菜单handle的测试不能证明未注册用户实际可达菜单。
2. config.public.example.yaml没有在allowed_plugins和system_plugins中配置welcome。auto_friend只同意好友申请，不发注册欢迎；注册插件也不负责好友通知，因此候选配置漏掉欢迎步骤。

这两项对应当前开发清单R1/R2，属于已有注册需求的修复，不是扩展首版范围。

实施中真实入口测试进一步发现：resolve_event_type把好友request也归为message，注册检查误拦auto_friend，导致补齐welcome后仍无法自动通过申请。关联修复在main中仅对post_type=message调用注册检查；保持全局事件分类不变，不将auto_friend加入未注册消息白名单。

## What Changes

- 注册检查仅用于真正的消息，不拦好友请求；不改变部署许可和其他准入限制。
- 未注册私聊的允许集合使用实际插件标识register、menu，同步误导性注释和原来固定错误标识的测试断言。
- 公开配置同时将welcome加入部署允许名单和系统集合，使新好友在尚未注册、没有账号插件设置时仍能收到欢迎。
- 保留三方职责：auto_friend同意请求；welcome在friend_add通知后发送现有文案包欢迎；register仅在用户主动发注册指令后开始流程。
- 用实际main.plugin_pool入口、真实插件注册标识和公开模板派生配置补回归，不仅验证字符串或直接调用handle。
- 同步插件状态查询测试：未注册目标的menu不应再被误报为注册限制；部署禁止仍不得绕过。

## Capabilities

### New Capabilities
无。

### Modified Capabilities
- `community-registration`：明确未注册菜单可从真实消息入口到达，以及公开模板欢迎配置和职责边界。

## 范围与兼容

不更改协议正文、所有者定稿文案、注册停顿、协议同意、发包、奖励或资料卡逻辑。不修改权限，不提前注册、不提前开启基础包，不改变群审核；不增加edition分支。

不自动改写任何部署现有config.yaml。已部署公开实例需按操作说明核对welcome两份名单并重启；仅更新示例不会修改实际配置。不因注册require开启而强制所有自定义部署启用welcome，也不扩大启动校验规则。

“一次欢迎”指一次friend_add事件仅由welcome负责发送；不承诺上游重投事件的跨事件去重或重启恢复，不引入额外存储。

## 验收标准

以下测试在实施阶段新增或调整，当前并未执行：

| 标准 | 独立执行 | 通过条件 |
|---|---|---|
| AC01 | `python -m pytest test/test_registration_entry.py -k menu_entry` | require开启，未注册普通账号经实际事件入口发送/菜单及/菜單，真实MenuPlugin收到调用；仅显示注册与菜单，不显示打卡等业务；无账户、同意凭证或插件覆盖新增 |
| AC02 | `python -m pytest test/test_registration_entry.py -k boundary` | 即使人为预先开启基础插件，未注册/打卡仍不执行并遵守已有提醒规则；部署禁止menu时不能绕过；require关闭、已注册、超管、群消息按既有规则运行 |
| AC03 | `python -m pytest test/test_registration_entry.py -k welcome_flow` | 公开模板隔离加载后好友请求只同意、不发欢迎或注册；一条friend_add只产生一条现有文案包欢迎，不重复同意；两事件均不写账号、协议凭证或开启基础包；随后主动/注册才开始流程，仍需同意才能登记 |
| AC04 | `python -m pytest test/test_deployment_templates.py test/test_register_gate.py test/test_plugin_query_scope.py test/test_register_flow.py test/test_enabled_menu.py test/test_text_pack.py` | 模板welcome属于允许名单和系统集合；原注册/菜单/查询断言同步，部署限制及内置私有欢迎文案不变；临时配置的所有数据库和媒体路径隔离 |
| AC05 | `python -m pytest`及`openspec validate registration-entry-fixes --strict` | 全量回归绿、逐项记录、临时副本归档检查通过；patch版本及CHANGELOG、相关规范/知识库/操作手册同步；实现与正式归档同commit |

## 维护者可持续性影响

减少新用户添加好友后没有引导、未注册菜单不可达造成的人工解释。无新增运行服务、队列、数据库表或配置键；不扩大运维承诺。真实QQ送达留作M2试运行，模拟接口通过不得表述为已完成真实联调。
