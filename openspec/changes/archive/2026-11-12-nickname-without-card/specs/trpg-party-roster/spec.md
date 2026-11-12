# trpg-party-roster — 变更（无名片回落）

## ADDED Requirements

### Requirement: 无名片时回落昵称
记录 DM/观察者昵称时 SHALL 优先使用群名片，名片为空时使用 QQ 昵称。收到 `group_card` 通知且 `card_new` 为空（用户取消了群名片）时，系统 SHALL 按群查询一次成员显示名并写入 `role_names`；查询失败或返回空时 MUST 保留原昵称。昵称与 QQ 号都取不到时，可回落 `用户<QQ号>`。

#### Scenario: DM 取消群名片
- **WHEN** DM 取消群名片，机器人收到 `card_new` 为空的 `group_card` 通知，且能查到 QQ 昵称
- **THEN** 准备名单显示 QQ 昵称，而不是已取消的旧名片

#### Scenario: 查不到昵称
- **WHEN** 取消名片后接口不可用
- **THEN** 保留原昵称，不影响其它流程

#### Scenario: 从未设置名片就发 .dm
- **WHEN** 没有群名片的成员发送 `.dm`
- **THEN** 记录其 QQ 昵称
