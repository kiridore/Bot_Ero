# coc-character-sheet — 变更（职业详情）

## ADDED Requirements

### Requirement: 角色卡展示职业详情
角色卡查看页 SHALL 展示职业详情区块，含：职业名、信用评级区间、技能点公式、职业介绍、本职技能清单、可选池已选项、推荐关系人、职业点与兴趣点用量。字段缺失时 MUST 省略对应行而不显示占位符。职业详情 SHALL 由 `occupation_by_name()` 一并返回，MUST NOT 依赖前端另建数据源。

#### Scenario: 会计师
- **WHEN** 查看一张职业为会计师的卡
- **THEN** 显示「会计师 · 信用评级 30-70 · 技能点 教育×4」、职业介绍、「本职技能：…」、「推荐关系人：生意伙伴…」与职业点用量

#### Scenario: 职业没有介绍
- **WHEN** 该职业在新卡里没有介绍与关系人
- **THEN** 这两行不出现，其余信息照常

#### Scenario: 可选池
- **WHEN** 卡的 `occupation_choices` 里选了「魅惑」
- **THEN** 页面显示「可选池已选：魅惑」
