# community-registration Specification

## Purpose
让公开实例的私聊用户经一次性自助注册获得使用资格：阅读并同意《用户协议》、留下同意凭证、从一个最小功能集开始。私有部署不开启该要求时行为完全不变。

## Requirements

### Requirement: 注册指令开启会话流程
`/注册` SHALL 仅在私聊中开始注册流程；群聊中发送 SHALL 回复私聊引导且不进入流程。流程中文案（含 `*写写*` 星号）SHALL 按所有者定稿逐句原样输出，段间停顿 2–3 秒、协议合并转发后停顿 5 秒；《用户协议》SHALL 以合并转发形式发送。

#### Scenario: 私聊开始注册
- **WHEN** 未注册用户私聊发送 /注册
- **THEN** 依次收到流程预告、协议引导、协议合并转发与同意指引，之后等待 /同意EULA

#### Scenario: 群聊发送注册指令
- **WHEN** 任意用户在群聊发送 /注册
- **THEN** 收到"请先添加我为好友，在私聊中完成注册~"，不进入流程

### Requirement: 同意指令完成注册并持久化凭证
`/同意EULA` SHALL 大小写不敏感；同意时 SHALL 在 `user_accounts` 写入 `eula_version` 与 `agreed_at`（不可改写首次时间），为该账号播种 `register.default_pack` 定义的功能包，并发布注册完成通知；已注册用户再次发送 SHALL 回复已完成。

#### Scenario: 完成注册
- **WHEN** 会话等待中的用户发送 /同意eula
- **THEN** 注册完成、播种默认包、收到收尾文案；eula_version 与 agreed_at 持久化

#### Scenario: 重复同意
- **WHEN** 已注册用户发送 /同意EULA
- **THEN** 回复"你已经完成注册啦"，无重复播种与再次写入

### Requirement: 注册会话为内存态且重启安全
会话状态 SHALL 存于内存（账号 → 当前步骤），重启丢失后 MUST 可经 /注册 重新开始；未持久化的同意 MUST 视为未同意。

#### Scenario: 流程中重启
- **WHEN** 会话等待同意时进程重启
- **THEN** 下次 /注册 从头开始，无半注册状态残留

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

### Requirement: 注册完成通知与资料卡
注册完成 SHALL 经内部通知发布；`personal_records` 插件在对外开放时 SHALL 为新账号发送资料卡（空数据渲染全零卡），未开放时 SHALL 静默跳过且收尾文案照常。

#### Scenario: 资料卡插件开放
- **WHEN** 注册完成且 personal_records 对该账号开放
- **THEN** 用户收到生成的资料卡

#### Scenario: 资料卡插件未开放
- **WHEN** 注册完成且 personal_records 未开放
- **THEN** 无资料卡、无错误提示，收尾文案正常送达

### Requirement: 启动校验注册配置
`register.require` 为 true 时，`eula_file` MUST 存在且可读，`default_pack` MUST 是已定义功能包；违反时启动 SHALL 失败并明确报错。配置节字段类型错误 SHALL 被统一校验拒绝。

#### Scenario: 协议文件缺失
- **WHEN** require=true 且 eula_file 指向不存在的文件
- **THEN** 启动退出并提示文件路径
