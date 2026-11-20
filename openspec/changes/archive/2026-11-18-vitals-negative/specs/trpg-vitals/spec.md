# trpg-vitals — 变更（数值表达式下限与明细）

## ADDED Requirements

### Requirement: 数值表达式合计不小于 0
`.hp`、`.san`、`.mp`、`.sc` 的骰子表达式（`1d4+1`、`2d6-3` 等）SHALL 以 `max(合计, 0)` 作为实际数值。合计为负时 MUST NOT 反向加减（扣血不得变成回血），`.sc` 的今日累计损失 MUST NOT 为负。

#### Scenario: 负合计不回血
- **WHEN** 玩家发送 `.san -1d4-2` 且 d4 掷出 1
- **THEN** SAN 不变，回执显示 `-d4-2=-1→0（1-2）`

#### Scenario: 正号负合计不扣血
- **WHEN** 玩家发送 `.san +1d4-3` 且 d4 掷出 1
- **THEN** SAN 不变

### Requirement: 带修饰的回执显示构成
表达式带数字修饰时，回执明细 SHALL 写出骰子点数与修饰的构成（`d4+1=4（3+1）`），未带修饰时保持 `d4=3` 的简写。

#### Scenario: 理智检定带修饰
- **WHEN** 玩家发送 `.sc 1/1d4+1`，检定失败且 d4 掷出 3
- **THEN** 回执含 `SAN 50 → 46` 与 `d4+1=4（3+1）`
