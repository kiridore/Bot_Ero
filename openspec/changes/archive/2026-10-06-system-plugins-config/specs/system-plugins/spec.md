# system-plugins · Spec Delta

## ADDED Requirements

### Requirement: 系统插件集可配置

系统插件集合 SHALL 由 `bot.system_plugins` 配置决定：非空列表时集合精确等于该列表（替换语义，非并集）；键缺失或空列表时回落内置缺省集（menu、group_manager、startup_changelog、backup、update、auto_friend、welcome、message_logger）。

#### Scenario: 未配置回落缺省集

- **WHEN** 配置不含 `bot.system_plugins`（或为空列表）
- **THEN** 系统插件集合等于内置缺省 8 项，行为与配置化之前完全一致

#### Scenario: 自定义列表精确替换

- **WHEN** 配置 `bot.system_plugins` 为非空列表
- **THEN** 系统插件集合精确等于该列表，未列入的缺省项不再是系统插件

### Requirement: 移出集合的插件回归按群开关

插件不在系统插件集合内时，其启用状态 SHALL 回归既有按群开关机制（`group_plugin_config` 表），meta 事件照常直达全部插件（心跳语义不变）。

#### Scenario: 移出项不再免检

- **WHEN** 某插件（如 message_logger）被配置移出系统插件集合，且群内未开启它
- **THEN** 该插件对该群的非 meta 事件不运行，meta 事件仍运行（心跳绕过启用检查为既有语义）
