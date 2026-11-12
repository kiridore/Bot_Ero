# trpg-preparation — 变更（角色昵称持久化）

## ADDED Requirements

### Requirement: 角色标记保存昵称
`pending.json` SHALL 在 `roles` 之外记录 `role_names`（`{用户ID: 昵称}`），用于 DM 与观察者——这两类身份不需要准备，没有准备快照可回落昵称。设置角色时 SHALL 写入发送者昵称；同一用户改设角色 MUST 更新昵称；弹劾/替换 DM 时 MUST 清除旧 DM 的昵称；清除角色时 MUST 一并清除昵称。缺少 `role_names` 的旧文件 MUST 按空处理且不报错。

#### Scenario: 设置 DM
- **WHEN** 老张在群里发送 `.dm`
- **THEN** `pending.json` 中 `roles` 为 `{"老张的QQ": "dm"}`，`role_names` 为 `{"老张的QQ": "老张"}`

#### Scenario: 换人当 DM
- **WHEN** 小王随后发送 `.dm`
- **THEN** `roles` 只保留小王，`role_names` 中老张的条目被删除

#### Scenario: 旧文件兼容
- **WHEN** 读取没有 `role_names` 字段的 `pending.json`
- **THEN** 正常返回，准备名单回落显示 QQ 号
