# trpg-preparation Specification

## Purpose
定义开团前准备阶段（DM 标记、准备名单、准备卡片、开录校验）的成员口径与展示规则。

## Requirements

### Requirement: 成员口径统一剔除机器人
统计群成员时必须剔除机器人：包括 `is_robot` 为真的账号与机器人自身。准备卡片的「已准备 x/y」分母、未准备 @ 列表，以及开录校验的成员集合 SHALL 使用同一份过滤结果。成员接口不可用时 MUST 保持原有降级：卡片提示名单不可用，开录拒绝并提示可强制开始。

#### Scenario: 机器人不进未准备名单
- **WHEN** 群里除人类成员外还有机器人（含本机器人）
- **THEN** 准备卡片的分母只计人类成员，未准备列表不出现任何机器人 QQ

#### Scenario: 接口不可用
- **WHEN** `get_group_member_list` 调用失败
- **THEN** 卡片显示「（成员名单不可用，未准备者未知）」，开录被拒绝并可改用强制开始

#### Scenario: 开录校验一致
- **WHEN** DM 发送 `/跑团 记录 开始`
- **THEN** 校验的成员集合与准备卡片一致（同样剔除机器人）

### Requirement: 角色标记保存昵称
`pending.json` SHALL 在 `roles` 之外记录 `role_names`（`{用户ID: 昵称}`），用于 DM 与观察者——这两类身份不需要准备，没有准备快照可回落昵称。设置角色时 SHALL 写入发送者昵称；同一用户改设角色 MUST 更新昵称；弹劾/替换 DM 时 MUST 清除旧 DM 的昵称；清除角色时 MUST 一并清除昵称。缺少 `role_names` 的旧文件 MUST 按空处理且不报错。

#### Scenario: 设置 DM
- **WHEN** 老张在群里发送 `.dm`
- **THEN** `pending.json` 中 `roles` 为 `{"老张的QQ": "dm"}`，`role_names` 为 `{"老张的QQ": "老张"}`

#### Scenario: 换人当 DM
- **WHEN** 小王随后发送 `.dm`
- **THEN** `roles` 只保留小王，`role_names` 中老张的条目被删除

#### Scenario: 旧文件兼容
- **WHEN** 读取没有 `role_names` 字段的 `pending.json`
- **THEN** 正常返回，准备名单回落显示 QQ 号
