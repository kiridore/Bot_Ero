# coc-character-sheet — 变更（克苏鲁神话不是技能）

## ADDED Requirements

### Requirement: 克苏鲁神话只存在于背景字段
克苏鲁神话 MUST NOT 出现在标准技能表、建卡页技能列表、`finalize` 的技能结果与 `default_skills` 播种名单中；它的数值 MUST 只存放在角色卡的 `cthulhu_mythos` 字段（建卡页「背景」区），并继续用于 `max_san = 99 − cthulhu_mythos`。

#### Scenario: 新建卡
- **WHEN** 打开建卡页
- **THEN** 技能表里没有「克苏鲁神话」一行，背景区有「克苏鲁神话」输入框

#### Scenario: 查看卡
- **WHEN** 查看一张 `cthulhu_mythos = 12` 的卡
- **THEN** 背景区块显示「克苏鲁神话：12」，技能表里没有该行

### Requirement: 旧卡的克苏鲁神话技能行要迁移
若角色卡仍有「克苏鲁神话」技能行，保存或打开时 MUST 把该行的点数（基础+成长+职业+兴趣）折进 `cthulhu_mythos`（取较大值）并移除该行，MUST NOT 静默丢失点数。

#### Scenario: 旧卡保存
- **WHEN** 卡上 `cthulhu_mythos = 5` 且技能行「克苏鲁神话」兴趣点 18，用户保存
- **THEN** 保存后 `cthulhu_mythos = 18`，技能行消失

### Requirement: `.ra 克苏鲁神话` 读背景字段
用 `.ra 克苏鲁神话` 检定时 MUST 使用 `cthulhu_mythos` 的值，且不产生成长标记。

#### Scenario: 神话检定
- **WHEN** 玩家发送 `.ra 克苏鲁神话`
- **THEN** 按卡上 `cthulhu_mythos` 作为目标值检定
