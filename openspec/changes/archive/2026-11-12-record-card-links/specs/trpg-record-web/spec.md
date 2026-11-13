# trpg-record-web — 变更（角色卡入口）

## ADDED Requirements

### Requirement: 参与者角色卡可点击查看详情
记录详情页 SHALL 为带 `char_id` 的参与者提供角色卡入口：参团角色卡条目本身是链接，聊天气泡头像外层也是链接，目标均为 `/trpg/char/<user_id>/<char_id>`。悬停时 SHALL 显示概要：COC 为「角色名 · 职业 · 年龄 · HP/SAN/MP 当前/上限」，DND 为「角色名 种族 职业 Lv.N · HP · AC」，取开录快照（缺失时用结束快照）；两者都没有时显示「本场没有角色卡快照」。没有 `char_id` 的参与者（如机器人）MUST NOT 生成链接。

#### Scenario: 点开参团角色卡
- **WHEN** 用户展开「参团角色卡」并点击某位参与者
- **THEN** 打开该参与者的角色卡详情页 `/trpg/char/<user_id>/<char_id>`

#### Scenario: 头像悬停与点击
- **WHEN** 鼠标停在他人头像上 / 点击头像
- **THEN** 前者显示角色概要，后者进入角色卡详情页

#### Scenario: 机器人
- **WHEN** 记录里有机器人消息
- **THEN** 机器人消息不产生角色卡链接

#### Scenario: 卡片不公开
- **WHEN** 目标角色卡设置了不公开
- **THEN** 详情页显示既有「对方未公开角色卡」提示，记录页快照不受影响
