# trpg-record-web — 变更（气泡头像与名称）

## ADDED Requirements

### Requirement: 气泡头像与名称
记录详情的气泡 SHALL 使用与论坛、时间线一致的 QQ 头像（通过 OneBot 解析），头像不可用时回落为名字首字色块。参与者名 SHOULD 显示为「角色卡名称（QQ名称）」；括号内的 QQ 名称 MUST 使用实时解析结果，解析失败时回落消息自带昵称。接口 SHALL 在 `participants` 中提供 `display_name` 与 `avatar_url`，且 MUST NOT 因解析失败而报错。

#### Scenario: 有头像
- **WHEN** 参与者能从 OneBot 取到头像地址
- **THEN** 气泡左侧渲染 `IMG.trpg-avatar`，`src` 为该地址

#### Scenario: 取不到头像
- **WHEN** 头像解析失败或为空
- **THEN** 渲染首字色块，页面无报错

#### Scenario: 名字格式
- **WHEN** 发送者有角色卡且其当前 QQ 名称为「老张」
- **THEN** 显示「艾拉（老张）」；没有角色卡时只显示「老张」
