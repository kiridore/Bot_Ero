# trpg-party-roster — 变更（准备中卡片排除机器人）

## ADDED Requirements

### Requirement: 准备中卡片只列真人
`/api/trpg/parties` 返回的准备中成员名单 SHALL NOT 包含任何机器人账号：`is_robot` 为真的成员 MUST 排除；机器人**自己的账号**（配置项 `bot.qq`）MUST 无论 `is_robot` 是否标记都被排除。

#### Scenario: 机器人自己的账号不带 is_robot
- **WHEN** OneBot 成员列表里机器人自己的账号 `is_robot` 为 false
- **THEN** 该账号不出现在准备中名单里

#### Scenario: 其他机器人账号
- **WHEN** 群里有另一个 `is_robot: true` 的账号
- **THEN** 同样不出现在名单里
