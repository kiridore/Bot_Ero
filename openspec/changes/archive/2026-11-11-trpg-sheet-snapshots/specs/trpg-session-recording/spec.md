# trpg-session-recording — 变更（参与者角色卡快照）

## ADDED Requirements

### Requirement: 记录保存参团角色卡快照
每条记录 SHALL 在 `meta.participants` 中保存参与者的 `char_id` 与两份角色卡快照：开录时的 `sheet_start` 与结束时的 `sheet_end`。快照 MUST 按卡片规则压缩（不含笔记、装备清单、特性长文本），至少包含属性、HP/AC 或 SAN/MP 等核心数值与技能（COC 为成功率）。录制中途才发言的参与者 SHALL 以首次发言时的卡作为 `sheet_start`。结束时若角色卡已被删除，SHALL 保留 `sheet_start` 并跳过 `sheet_end`；快照失败 MUST NOT 阻断结束流程。

#### Scenario: 开录写入起始快照
- **WHEN** DM 用 `/跑团 记录 开始` 成功开录
- **THEN** `meta.participants` 每个参与者含 `char_id` 与 `sheet_start`（含等级/HP 或 SAN/技能）

#### Scenario: 结束写入终态快照
- **WHEN** 群内发送 `/跑团 记录 结束`
- **THEN** 同一记录每个参与者补上 `sheet_end`，可与 `sheet_start` 对比

#### Scenario: 角色卡被删除
- **WHEN** 结束前玩家删除了角色卡
- **THEN** 该参与者保留 `sheet_start`，`sheet_end` 缺失，结束流程照常完成

#### Scenario: 网页查看
- **WHEN** 打开该记录详情
- **THEN** 可展开「参团角色卡（开始 / 结束）」查看两份数值与本场变化
