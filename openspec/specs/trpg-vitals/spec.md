# trpg-vitals Specification

## Purpose
让跑团中的数值变动可执行、可追溯：HP 与 SAN 的扣减/恢复走群指令，COC 理智检定一条指令完成，变动写进跑团记录；越界与状态在回执里说清楚。

## Requirements

### Requirement: HP 与 SAN 变动指令
系统 SHALL 提供 `.hp <±值|满> [@目标]`（DND 与 COC 卡通用）与 `.san <±值|满> [@目标]`（仅 COC 卡）。数值 MUST 支持骰子表达式（`NdM`、`NdM±K`、纯数字），变动结果 MUST 截断在 `0 .. 上限`，`满` MUST 恢复为上限。未带正负号且不是 `满` 时 SHALL 拒绝并给出示例。

#### Scenario: 扣血
- **WHEN** 当前 HP 20 的玩家发送 `.hp -5`
- **THEN** 卡片 `current_hp` 变为 15，回执为「HP 20 → 15（-5）」

#### Scenario: 归零状态
- **WHEN** 当前 HP 3 的玩家发送 `.hp -99`
- **THEN** `current_hp` 为 0，回执额外含「HP 归零：昏迷」（DND 卡）或「HP 归零：濒死」（COC 卡）

#### Scenario: 回满
- **WHEN** 玩家发送 `.hp 满`
- **THEN** `current_hp` 等于卡片上限，回执含「已回满」

### Requirement: 权限与规则门控
改自己 SHALL 始终允许；改他人 MUST 要求发送者是本团 DM 或超级用户（通过 `@` 指定目标）。卡片规则与本团规则不一致时 SHALL 拒绝并说明；DND 卡上执行 `.san` / `.sc` SHALL 被拒绝。

#### Scenario: 玩家无权改他人
- **WHEN** 非 DM 玩家发送 `.hp -5 @DM`
- **THEN** 回执「只有 DM 可以修改他人的数值」，目标卡片不变

#### Scenario: 规则不符
- **WHEN** 本团规则为 COC 7th，玩家对 DND 卡发送 `.hp -5`
- **THEN** 回执说明本团规则与卡片规则不一致，不修改卡片

### Requirement: COC 理智检定
`.sc <成功损失>/<失败损失>` SHALL 掷 D100 与当前 SAN 比较：`D100 ≤ 当前 SAN` 为成功，扣成功损失；否则扣失败损失。回执 MUST 含检定骰、当前 SAN、成功/失败、扣减后 SAN 与损失算式，并 MUST 给出「今日累计损失 / 不定时疯狂线（当前 SAN 的 1/5）」；一次性损失 ≥5 时 MUST 提示是否需要灵感检定由 DM 决定；SAN 归零 MUST 提示永久疯狂。系统 MUST NOT 自动判定疯狂类型。

#### Scenario: 检定成功
- **WHEN** 当前 SAN 65 的玩家发送 `.sc 1/1d6`，D100 掷出 42
- **THEN** 回执含「成功」，SAN 变为 64

#### Scenario: 检定失败且损失超过 5
- **WHEN** 当前 SAN 65 的玩家发送 `.sc 0/1d10`，D100 掷出 99，损失骰掷出 6
- **THEN** SAN 变为 59，回执含「一次性损失 ≥5」与今日累计损失

#### Scenario: 理智归零
- **WHEN** 当前 SAN 2 的玩家检定失败并损失 10
- **THEN** `current_san` 为 0，回执含「SAN 归零：永久疯狂」

### Requirement: 当前值存储与展示
COC 卡 SHALL 持久保存 `current_hp` / `current_mp` / `current_san`，缺省等于各自上限，越界写入 MUST 被截断。建卡页 SHALL 只读展示「当前 / 上限」，MUST NOT 提供改值入口（写入通道仅限 bot 进程）。

#### Scenario: 新建调查员
- **WHEN** 用户新建 COC 卡且未填写当前值
- **THEN** 保存后 `current_san` 等于意志值、`current_mp` 等于 `意志//5`、`current_hp` 等于 `(体质+体型)//10`

#### Scenario: 已受伤的卡
- **WHEN** 用户提交 `current_san=40`、`current_hp=6`
- **THEN** 存回的正是 40 与 6，而不是被重置为上限

### Requirement: 记录联动
录制期间执行数值指令时，回执内容 SHALL 作为机器人消息写入当日跑团记录；无录制时 MUST 静默跳过。

#### Scenario: 录制中扣血
- **WHEN** 群正在录制时玩家发送 `.hp -5`
- **THEN** `messages.jsonl` 中出现 `sender_type: "bot"` 的「HP 20 → 15（-5）」记录
