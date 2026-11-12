# trpg-session-recording — 变更（群名）

## ADDED Requirements

### Requirement: 群名落盘与展示
准备状态文件 SHALL 记录群名（`group_name`），用于网页准备名单展示——webapp 是独立进程，MUST NOT 依赖 OneBot 调用取群名。群名缺失时 MUST 回落显示 `群 <群号>`，且 MUST NOT 影响任何流程。记录 `meta.json` 的群名在结束录制与启动恢复时 SHALL 尝试补写一次（当且仅当当前为空且能取到）。

#### Scenario: 准备中卡片显示群名
- **WHEN** 群主设置 DM 后刷新 `/trpg/records`
- **THEN** 准备中卡片标题显示群名，而不是「群 296470819」

#### Scenario: 取不到群名
- **WHEN** OneBot 接口不可用、群名解析为空
- **THEN** 卡片回落显示「群 <群号>」，准备状态与录制流程照常

#### Scenario: 结束录制补名
- **WHEN** 开录时群名解析失败导致 `meta.group_name` 为空，结束录制时接口恢复可用
- **THEN** 结束时补写群名，记录卡片显示群名
