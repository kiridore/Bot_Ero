# coc-character-sheet — 变更（查看页 COC 渲染）

## ADDED Requirements

### Requirement: 查看页按规则渲染
`/trpg/char/<用户>/<编号>` SHALL 依据角色卡 `rules` 字段选择渲染方式：`coc7th` 使用调查员卡视图，`dnd5e` 保持原有 DND 视图。COC 视图 MUST 展示调查员信息、派生数值、九项属性、技能（含成长标记与成功率）、武器（类型、使用技能、伤害含伤害加值标注、射程、次数、装弹量、故障值、贯穿）、资产、背景与笔记。

#### Scenario: 打开 COC 卡
- **WHEN** 访问一张 `rules=coc7th` 的角色卡
- **THEN** 页面标题为「【姓名】职业」，状态行显示 HP/MP/SAN 当前与上限、MOV、伤害加值、体格、闪避、信用评级

#### Scenario: 属性九宫格
- **WHEN** 查看 COC 卡属性区
- **THEN** 按力量/敏捷/意志、体质/外貌/教育、体型/智力/幸运 3×3 排列

#### Scenario: 武器伤害含 DB
- **WHEN** 武器伤害写作 `2D6+DB` 且卡片伤害加值为 +1D4
- **THEN** 显示为 `2D6+DB（DB=+1D4）`

#### Scenario: DND 卡不受影响
- **WHEN** 访问一张 `rules=dnd5e` 的角色卡
- **THEN** 仍显示等级/种族/职业/AC/豁免等原有 DND 区块
