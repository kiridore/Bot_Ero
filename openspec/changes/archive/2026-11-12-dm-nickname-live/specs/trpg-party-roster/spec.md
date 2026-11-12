# trpg-party-roster — 变更（昵称实时刷新）

## ADDED Requirements

### Requirement: 群名片变更实时刷新昵称
收到 OneBot `group_card` 通知时，系统 SHALL 把 `card_new` 写入该群 `pending.json` 的 `role_names`，但 MUST 仅在该用户已有 DM 或观察者标记时写盘；`card_new` 为空或与该用户当前昵称相同时 MUST NOT 写盘。其它 notice 类型 MUST NOT 触发本逻辑。

#### Scenario: DM 改名片
- **WHEN** DM 在本群修改群名片
- **THEN** `pending.json.role_names[DM]` 更新为新名片，网页准备名单显示新名字

#### Scenario: 普通成员改名片
- **WHEN** 没有 DM/观察者标记的成员修改群名片
- **THEN** 不写入任何文件

#### Scenario: 空名片
- **WHEN** 通知里 `card_new` 为空
- **THEN** 保留原有昵称
