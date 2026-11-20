# trpg-vitals — 变更（幸运增减）

## ADDED Requirements

### Requirement: `.幸运` 增减幸运
`.幸运 <±值> [@目标]`（别名 `.luck`）SHALL 修改 COC 7th 角色卡的幸运值：数值 MUST 带正负号，支持固定值与骰子表达式；结果 MUST 截断在 0–99，且花超/加超时给出提示。该指令 MUST 只对 COC 7th 角色卡生效，且 `@他人` MUST 需要本群 DM 或超级用户；回执 MUST 写入跑团记录。

#### Scenario: 花掉幸运
- **WHEN** 幸运 45 的玩家发送 `.幸运 -10`
- **THEN** 卡上幸运变为 35，回执 `幸运 45 → 35（-10）`

#### Scenario: 花超
- **WHEN** 幸运 5 的玩家发送 `.幸运 -50`
- **THEN** 幸运变为 0，回执附「幸运已见底（不会低于 0）」

#### Scenario: 用错规则
- **WHEN** DND 5E 角色卡发送 `.幸运 -5`
- **THEN** 拒绝并提示幸运是 COC 7th 的数值
