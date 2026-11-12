# coc-character-sheet — 变更（当前值保存语义）

## ADDED Requirements

### Requirement: 当前值三态语义
请求体中的 `current_hp` / `current_mp` / `current_san` SHALL 区分三种状态：未提供（`None`）、显式 `0`、显式正整数。新建角色卡时未提供 MUST 按上限初始化；编辑角色卡时未提供 MUST 沿用卡上原值；显式值 MUST 原样保存（包括 0）。

#### Scenario: 新建
- **WHEN** 提交一张不带当前值的 COC 卡
- **THEN** `current_hp/current_mp/current_san` 等于上限

#### Scenario: 编辑
- **WHEN** 建卡页再次保存（不带当前值）
- **THEN** 三项保持卡上的原值，不被清零

#### Scenario: 濒死
- **WHEN** 请求显式传 `current_hp=0`
- **THEN** 卡上保存 0，不被改成上限

### Requirement: MP 变动指令
系统 SHALL 提供 `.mp <±值|满> [@目标]`，仅对 COC 卡生效，规则同 `.san`：改他人需要 DM 或超级用户，结果写入跑团记录。

#### Scenario: 施法消耗
- **WHEN** COC 玩家发送 `.mp -3`
- **THEN** 回执显示 `MP 13 → 10`

#### Scenario: 回满
- **WHEN** 发送 `.mp 满`
- **THEN** 当前 MP 恢复到上限

#### Scenario: 规则不符
- **WHEN** 当前卡是 DND 5E
- **THEN** 提示该指令为 COC 专用
