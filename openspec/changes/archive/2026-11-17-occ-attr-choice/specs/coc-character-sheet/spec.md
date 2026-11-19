# coc-character-sheet — 变更（本职属性选择）

## ADDED Requirements

### Requirement: 带「或」的职业由玩家指定本职属性
公式含「或」的技能点计算 SHALL 允许玩家通过卡片字段 `occupation_attr` 指定候选项之一；指定后预算 MUST 按该属性计算，未指定时 MUST 取候选项中的较高者。填写的属性不是该职业候选项时，保存 MUST 被拒绝并给出候选项。

#### Scenario: 猎人按力量
- **WHEN** 猎人卡（教育 80、力量 45、敏捷 70）设置 `occupation_attr = 力量`
- **THEN** 职业点预算为 250（教育×2＋力量×2）

#### Scenario: 未指定
- **WHEN** 同一张卡没有 `occupation_attr`
- **THEN** 预算为 300（取敏捷，与新卡的 MAX 一致）

#### Scenario: 属性不在候选项里
- **WHEN** 猎人卡设置 `occupation_attr = 意志`
- **THEN** 保存返回 400，提示只能选力量或敏捷

### Requirement: 自定义职业的第二职业属性
`自定义职业` SHALL 允许玩家指定第二职业属性（八属性之一或留空）；职业点预算 MUST 为 `教育×2＋第二属性×2`，留空时为 `教育×4`。

#### Scenario: 指定意志
- **WHEN** 自定义职业卡（教育 80、意志 65）设置第二职业属性为意志
- **THEN** 预算为 290

#### Scenario: 留空
- **WHEN** 没有指定第二职业属性
- **THEN** 预算为 320（教育×4）
