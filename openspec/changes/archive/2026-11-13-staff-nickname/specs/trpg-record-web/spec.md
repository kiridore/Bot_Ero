# trpg-record-web — 变更（DM / 观察者的姓名口径）

## ADDED Requirements

### Requirement: DM 与观察者显示群昵称
记录详情页中，`role` 为 `dm` 或 `ob` 的参与者 SHALL 只显示其群昵称：消息气泡的名字行、参团角色卡条目、悬停概要一律使用 `display_name`（缺失时回落 `nickname`），MUST NOT 拼接角色卡名。其他参与者 SHALL 保持「角色名（昵称）」或角色名。角色徽标（DM / 观察者）继续显示。

#### Scenario: DM 发言
- **WHEN** DM 有角色卡「艾拉」、群昵称「老张」
- **THEN** 气泡名字行显示 `老张`，不显示 `艾拉（老张）`

#### Scenario: 观察者发言
- **WHEN** 观察者同时有角色卡
- **THEN** 气泡、参团角色卡条目与悬停概要都只显示群昵称

#### Scenario: 玩家发言
- **WHEN** 普通玩家有角色卡
- **THEN** 仍显示「角色名（昵称）」
