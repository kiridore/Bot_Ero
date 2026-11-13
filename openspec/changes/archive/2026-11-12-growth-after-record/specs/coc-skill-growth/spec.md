# coc-skill-growth — 变更（结算门控）

## ADDED Requirements

### Requirement: 不在录制中时按卡片规则结算
`/跑团 成长` 的本团规则检查 SHALL 只在**该群正在录制**时生效；不在录制中时 MUST 以角色卡自身的 `rules` 字段为准（COC 卡即可结算），MUST NOT 因群规则回落默认值而拒绝。录制中且本团规则不是 COC 7th 时仍 SHALL 拒绝并保留标记。

#### Scenario: 结束后补结算
- **WHEN** 录制已结束（`pending.json` 已不存在、群规则回落 DND），玩家发送 `/跑团 成长` 且卡是 COC、带成长标记
- **THEN** 正常结算并给出掷骰明细，标记被清空

#### Scenario: DND 录制中
- **WHEN** 正在以 DND 5E 录制的群里对 COC 卡发送 `/跑团 成长`
- **THEN** 提示「幕间成长需要 COC 7th」，不结算、标记保留
