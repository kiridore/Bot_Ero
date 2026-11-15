# trpg-record-web — 变更（参团角色卡不列观察者）

## ADDED Requirements

### Requirement: 参团角色卡排除观察者
记录详情页的「参团角色卡」区块 SHALL 只列出参与者（DM 与玩家），`role` 为 `ob` 的观察者 MUST NOT 出现在其中，即使他绑定了角色卡或有快照。

#### Scenario: 观察者带角色卡
- **WHEN** 观察者在本场绑定了角色卡并产生了快照
- **THEN** 「参团角色卡」里没有他的条目，消息流里的观战席样式不变

#### Scenario: DM 带角色卡
- **WHEN** DM 绑定了角色卡
- **THEN** 他的条目仍出现在「参团角色卡」里并可点开
