# system-plugins Specification

## Purpose
定义系统插件集合的配置与保护规则，并明确非系统插件在群聊、私聊公共默认和账号单独设置下如何决定是否运行。

## Requirements

### Requirement: 系统插件集可配置
系统插件集合 SHALL 由bot.system_plugins配置决定：非空列表精确替换，缺失或空列表使用现有内置集合。系统身份仅免除局部普通开关，不免除部署许可。生效的系统集合不在部署名单内时 SHALL 启动失败并列出冲突，不静默放开权限。

#### Scenario: 未配置回落缺省集
- **WHEN** 配置没有system_plugins和allowed_plugins
- **THEN** 使用既有内置系统集合，旧配置可加载

#### Scenario: 自定义列表精确替换
- **WHEN** system_plugins提供合法非空列表
- **THEN** 集合精确等于该列表，不与缺省集合合并

#### Scenario: 部署禁止系统插件
- **WHEN** 生效的系统集合包含message_logger，而明确的部署名单排除它
- **THEN** 启动报错列出message_logger，不产生其业务行为

### Requirement: 移出集合的插件回归按群开关
非系统插件 SHALL 按实际作用的群或私聊账号判断局部启用；私聊账号没有覆盖时才沿用公共默认。meta事件 MUST NOT 无条件直达全部业务：部署禁止先过滤，具有群/账号对象的任务再检查该对象；明确的全局维护由部署范围控制。

#### Scenario: 移出项不再免检
- **WHEN** message_logger移出系统集合且当前群未开启
- **THEN** 不记录该群消息，也不能以其他事件类型绕过部署和作用范围检查

#### Scenario: 私聊账号覆盖默认
- **WHEN** 公共设置开启插件但超级用户为某账号单独关闭
- **THEN** 该账号私聊不运行该插件，其他账号及群聊不受影响

#### Scenario: 私聊账号恢复默认
- **WHEN** 超级用户移除账号单独设置
- **THEN** 该账号后续私聊采用公共设置，仍不能突破部署许可
