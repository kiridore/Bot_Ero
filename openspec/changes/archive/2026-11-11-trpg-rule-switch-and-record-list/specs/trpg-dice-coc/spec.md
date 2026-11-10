# trpg-dice-coc Specification

## Purpose
跑团骰子在 DND 5E 之外恢复 COC 7th：`.ra <技能值>` 技能检定（极限/困难/常规成功与大失败）、`.r c<技能值>` 与 `.rh c<技能值>` 两种等价写法、以及奖励骰与惩罚骰 `.r b<n>` / `.r p<n>`。规则的切换由 `trpg-rule-selection` 维护，本能力只负责按当前规则决定接受哪些检定指令。

## ADDED Requirements

### Requirement: COC 7th 技能检定
在当前规则为 `coc7th` 时，`.ra <技能值>`、`.r c<技能值>`、`.rh c<技能值>` SHALL 执行 COC 技能检定并输出掷骰结果与成功等级。技能值 MUST 为 1–100 的整数，越界 SHALL 报错且不掷骰。成功等级判定 SHALL 为：`roll <= 技能值/5`（向下取整，至少 1）为极限成功；`roll <= 技能值/2`（向下取整，至少 1）为困难成功；`roll <= 技能值` 为常规成功；`roll >= 96` 为大失败；否则为失败。`.rh` 形式 MUST 只在群内输出「悄悄掷出骰子」提示，结果只回私聊并在录制中作为暗骰入档。

#### Scenario: 常规检定
- **WHEN** 规则为 COC 7th，团友发送 `.ra 70`，掷出 42
- **THEN** 机器人输出技能检定结果，成功等级为常规成功

#### Scenario: 三种写法等价
- **WHEN** 规则为 COC 7th
- **THEN** `.ra 70`、`.r c70` 都输出技能检定；`.rh c70` 只在群里提示、结果走私聊

#### Scenario: 技能值越界
- **WHEN** 团友发送 `.ra 0` 或 `.ra 101`
- **THEN** 机器人报错「技能值应在1~100之间」，不掷骰

### Requirement: 奖励骰与惩罚骰
在当前规则为 `coc7th` 时，`.r b<n>`、`.r 1d100b<n>` SHALL 掷奖励骰，`.r p<n>`、`.r 1d100p<n>` SHALL 掷惩罚骰；省略数量时默认 1 颗，数量 MUST 在 1–10 之间，越界 SHALL 报错。算法 SHALL 与历史实现一致：以一次 D100 的个位与 N 颗个位骰组成候选，奖励取最大个位、惩罚取最小个位，结果超过 100 时按 100 计。

#### Scenario: 奖励骰
- **WHEN** 规则为 COC 7th，团友发送 `.r b2` 或 `.r 1d100b2`
- **THEN** 机器人输出奖励骰结果与参与比较的个位骰

#### Scenario: 数量越界
- **WHEN** 团友发送 `.r b0` 或 `.r p11`
- **THEN** 机器人报错，不掷骰

### Requirement: 规则门控
当前规则为 `dnd5e` 时，`.ra`、`.r b/p`、`.rh c<值>` MUST 被拒绝，并提示当前规则与切换方法（`/跑团 规则 coc7th`）。当前规则为 `coc7th` 时，`.rc` MUST 被拒绝并提示改用 `.ra <技能值>`。`.r` 通用掷骰与 `.rh` 通用暗骰 MUST 在两种规则下都可用。拒绝时 MUST NOT 产生任何掷骰结果。

#### Scenario: DND 规则下用 COC 指令
- **WHEN** 规则为 DND 5E，团友发送 `.ra 70`
- **THEN** 机器人提示当前规则是 DND 5E 并说明如何切换，不掷骰

#### Scenario: COC 规则下用 DND 指令
- **WHEN** 规则为 COC 7th，团友发送 `.rc 力量`
- **THEN** 机器人提示当前规则是 COC 7th、请用 `.ra <技能值>`，不掷骰
