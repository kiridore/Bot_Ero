# system-plugins Specification

## Purpose
定义系统插件集合的配置与保护规则，并明确非系统插件在群聊、私聊公共默认和账号单独设置下如何决定是否运行。

## Requirements

### Requirement: 系统插件集可配置

系统插件集合 SHALL 由 `bot.system_plugins` 配置决定：非空列表时集合精确等于该列表（替换语义，非并集）；键缺失或空列表时回落内置缺省集（menu、group_manager、startup_changelog、backup、update、auto_friend、welcome、message_logger）。

#### Scenario: 未配置回落缺省集

- **WHEN** 配置不含 `bot.system_plugins`（或为空列表）
- **THEN** 系统插件集合等于内置缺省 8 项，行为与配置化之前完全一致

#### Scenario: 自定义列表精确替换

- **WHEN** 配置 `bot.system_plugins` 为非空列表
- **THEN** 系统插件集合精确等于该列表，未列入的缺省项不再是系统插件

### Requirement: 移出集合的插件回归按群开关

插件不在系统插件集合内时，其非 meta 事件启用状态 SHALL 按所在位置判断：群聊使用既有按群开关机制（`group_plugin_config` 表）；私聊优先使用该账号的单独设置，没有单独设置时沿用私聊公共设置。账号设置 SHALL 支持开启、关闭、沿用默认，且仅超级用户可以修改。外部 meta 事件仍照常直达全部插件，本次不改变既有心跳派发规则；其产生的新奖励通知仍须遵守通知处理的启用规则。

#### Scenario: 移出项不再免检

- **WHEN** 某插件（如 message_logger）被配置移出系统插件集合，且群内未开启它
- **THEN** 该插件对该群的非 meta 事件不运行，外部 meta 事件仍直达插件

#### Scenario: 私聊账号覆盖默认

- **WHEN** 私聊公共设置开启一个非系统插件，但超级用户为某账号单独关闭它
- **THEN** 该账号私聊不运行该插件的非 meta 事件处理，其他账号仍沿用公共设置

#### Scenario: 私聊账号恢复默认

- **WHEN** 超级用户移除该账号的单独设置
- **THEN** 该账号后续私聊操作恢复沿用公共设置
