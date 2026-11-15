# trpg-session-recording — 变更（幕间成长指令可达）

## ADDED Requirements

### Requirement: 插件匹配必须覆盖全部已路由的子命令
`TrpgSessionPlugin.match()` SHALL 放行所有由 `_route()` 处理的 `/跑团` 子命令（`准备`、`取消准备`、`名单`、`规则`、`成长`、`记录`）以及裸 `/跑团`。新增子命令时 MUST 同步匹配范围，否则指令会在框架层被丢弃。未知子命令 MUST 保持不匹配。

#### Scenario: 幕间成长
- **WHEN** 玩家发送 `/跑团 成长`
- **THEN** 插件匹配并执行结算（录制中与录制外一致）

#### Scenario: 未知子命令
- **WHEN** 玩家发送 `/跑团 乱打`
- **THEN** 插件不匹配，不产生任何回复
