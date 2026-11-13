# trpg-party-roster — 变更（全员名单与可点开条件）

## ADDED Requirements

### Requirement: 准备中的卡片列出群里所有成员
`/api/trpg/parties` 返回的准备中名单 SHALL 包含该群全部真人成员（排除 `is_robot`），顺序为 DM → 观察者 → 已准备者（按准备时间）→ 其余按昵称。群成员接口不可用时 SHALL 退回 `pending.json` 中出现的 DM、观察者与已准备者。`member_count` SHALL 等于名单人数，`prepared_count` SHALL 只统计名单内已准备者。

#### Scenario: 群里有没准备的人
- **WHEN** 群里有 3 名真人与 1 个机器人，其中 1 人已准备
- **THEN** 名单 3 人（不含机器人），`prepared_count` 为 1

#### Scenario: 成员接口不可用
- **WHEN** OneBot 群成员接口返回失败
- **THEN** 名单仍是 DM、观察者与已准备者，页面不报错

### Requirement: 有当前角色卡即可查看
准备中卡片的每个成员 SHALL 解析出可查看的角色卡：已准备者用准备快照的卡，未准备者用其当前角色卡。前端 SHALL 在 `char_id` 存在时把整行做成链接（`/trpg/char/<用户>/<卡号>?party=<群号>`），未准备者额外标「未准备」；没有角色卡的人 MUST NOT 可点，显示「等待准备」。查看权限沿用既有规则：本人、本群 DM、超级用户可看，其他人按对方隐私设置。

#### Scenario: 没准备但设了卡
- **WHEN** 群成员从未 `/跑团 准备`，但网页上已建卡并设为当前
- **THEN** 他在准备中卡片里可点开看自己的卡，DM 也能审核

#### Scenario: 完全没卡
- **WHEN** 群成员还没建角色卡
- **THEN** 该行显示「等待准备」，不可点击
