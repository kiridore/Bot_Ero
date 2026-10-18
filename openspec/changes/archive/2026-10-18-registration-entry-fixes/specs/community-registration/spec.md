## MODIFIED Requirements

### Requirement: 私聊准入按配置启用
`register.require` 缺省 false；false 时 SHALL 不产生任何注册限制。开启时未注册账号的私聊消息 SHALL 仅放行注册与菜单插件，使用与运行时调度一致的插件标识，并且 MUST NOT 绕过部署允许范围。其他命令样式消息 SHALL 收到注册提醒，同一账号在 `register.reminder_minutes`（缺省 30）内只提醒一次；已注册账号、超级用户与群消息 SHALL 保持既有规则，不因本次修复扩大业务权限。未注册菜单 SHALL 只展示注册与菜单入口，不产生注册、同意凭证或基础包开启记录。

#### Scenario: 未注册菜单实际可达
- **WHEN** 未注册普通账号在要求注册且允许菜单插件的部署中私聊发送/菜单或/菜單
- **THEN** 经正常事件入口执行菜单插件并返回注册引导菜单，不展示业务条目，不自动注册或开启基础包

#### Scenario: 未注册使用其他指令
- **WHEN** 未注册用户私聊发送/打卡，即使该账号已有打卡插件开启设置
- **THEN** 业务插件不执行，收到一次注册提醒；限频窗口内再次发送不再提醒

#### Scenario: 部署禁止优先
- **WHEN** 菜单插件被部署名单禁止而未注册用户请求菜单
- **THEN** 注册允许入口不得重新启用该插件或发送菜单

#### Scenario: 好友请求不是注册受限消息
- **WHEN** 未注册用户发来好友申请，运行时将请求沿用message调度分类
- **THEN** 注册检查仅限制post_type为message的真实消息，不拦截部署允许且已启用的auto_friend处理请求

#### Scenario: 私有部署不受影响
- **WHEN** 未配置register节或require=false且未注册任何账号
- **THEN** 不增加注册限制，私聊指令仍按既有部署许可和插件开关执行

### Requirement: 欢迎消息经文案包覆盖
welcome插件 SHALL 经 `welcome.friend_add` 文案键输出；内置默认 SHALL 与现私有文案逐字节一致；公开部署由文案包覆盖为既有注册引导文案。公开配置模板 SHALL 在部署允许名单和系统插件集合中包含welcome，让新好友无账号单独设置时也能收到欢迎。auto_friend SHALL 负责同意好友请求，welcome SHALL 负责好友添加通知后的欢迎，register SHALL 等待用户主动使用注册指令；一条好友添加通知不得因多个插件职责重复而发送多份欢迎，不要求跨通知去重。

#### Scenario: 公开部署欢迎
- **WHEN** 按公开模板配置运行，收到一条friend_add通知且文案包包含welcome.friend_add
- **THEN** welcome仅发送一条覆盖后的欢迎文案，内容引导/注册，不登记账号、协议同意或开启基础包

#### Scenario: 申请通过不等于注册
- **WHEN** 收到好友请求但尚未收到好友添加通知，也没有用户注册指令
- **THEN** auto_friend处理同意，不发送欢迎或自动开始注册流程

#### Scenario: 用户主动开始
- **WHEN** 用户收到欢迎后主动私聊发送/注册
- **THEN** 才开始既有协议流程，仍须/同意EULA才能完成登记

#### Scenario: 禁用欢迎插件
- **WHEN** 自定义部署没有允许welcome
- **THEN** 不发送欢迎，不因修复公开模板而强制启用该插件
