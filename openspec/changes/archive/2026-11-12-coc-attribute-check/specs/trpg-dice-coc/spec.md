# trpg-dice-coc — 变更（属性检定）

## ADDED Requirements

### Requirement: `.ra` 支持属性名
`.ra <名字>` SHALL 依次尝试技能名与属性名。属性名包括中文全称（力量/体质/体型/敏捷/外貌/智力/意志/教育）、英文缩写（STR/CON/SIZ/DEX/APP/INT/POW/EDU，大小写不敏感）、幸运与信用评级（含别名「信用」）。回执 SHALL 用 `[<属性名>=<值>]` 标示取值来源；属性检定 MUST NOT 写入成长标记。目标值为 0 时 SHALL 提示无法检定。

#### Scenario: 属性检定
- **WHEN** COC 玩家发送 `.ra 力量`，其角色卡力量为 60
- **THEN** 回执形如 `D100=42 [力量=60] → 常规成功`，角色卡不被修改

#### Scenario: 英文缩写
- **WHEN** 发送 `.ra STR` 或 `.ra str`
- **THEN** 同样按力量数值检定

#### Scenario: 幸运与信用评级
- **WHEN** 发送 `.ra 幸运` / `.ra 信用评级`
- **THEN** 分别读取卡上的幸运与信用评级数值

#### Scenario: 零值
- **WHEN** 目标的数值是 0
- **THEN** 回执「无法检定（目标值需要 1 以上）」

### Requirement: COC 卡上 `.r` 不接受属性名
COC 规则下 `.r <属性名或技能名>` SHALL 被拒绝并提示改用 `.ra`，MUST NOT 输出 DND 属性加值。

#### Scenario: 误用 `.r`
- **WHEN** COC 玩家发送 `.r 力量`
- **THEN** 收到「COC 的属性与技能请用 .ra … 做检定」，不出现 25 这类加值数字
