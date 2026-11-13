# trpg-party-roster — 变更（准备卡片成员行）

## ADDED Requirements

### Requirement: 准备卡片的 DM / 观察者行不显示角色卡名
准备中的跑团卡片里，成员 `role` 为 `dm` 或 `ob` 时 MUST 只显示群昵称与角色徽标，MUST NOT 渲染角色卡名称，也 MUST NOT 显示「未选角色卡」占位。玩家成员保持昵称 + 角色卡名（未选时显示「未选角色卡」）。

#### Scenario: 观察者成员
- **WHEN** 准备卡片列出观察者
- **THEN** 该行显示「围观 [观察者]」，没有角色卡名称，也没有「未选角色卡」

#### Scenario: 玩家成员
- **WHEN** 玩家已准备并绑定角色卡
- **THEN** 该行仍显示角色卡名并可点开
