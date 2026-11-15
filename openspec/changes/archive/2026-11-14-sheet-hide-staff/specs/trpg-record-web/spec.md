# trpg-record-web — 变更（参团角色卡只列玩家）

## ADDED Requirements

### Requirement: 参团角色卡只列玩家
记录详情页的「参团角色卡」区块 SHALL 只列出 `role` 为空的参与者（玩家）。`role` 为 `dm` 或 `ob` 的成员 MUST NOT 出现在其中，即使绑定了角色卡或有快照。

#### Scenario: DM 带角色卡
- **WHEN** DM 在本场绑定了角色卡并产生快照
- **THEN** 「参团角色卡」里没有他的条目；他的消息气泡仍正常显示

#### Scenario: 玩家带角色卡
- **WHEN** 玩家绑定了角色卡
- **THEN** 该条目出现在「参团角色卡」并可点开
