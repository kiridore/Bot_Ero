# trpg-party-roster — 变更（角色卡描述）

## ADDED Requirements

### Requirement: 角色卡描述按规则生成
准备名单中角色名后的括号 SHALL 按角色卡规则选择字段：`coc7th` 显示「职业 · 年龄」，`dnd5e` 显示「种族 职业 Lv.等级」。字段缺失时 MUST 省略或给出明确占位，MUST NOT 输出连续问号；DND 卡三项均为空且等级为 1 时 MUST NOT 显示括号。旧快照缺少规则字段时 SHALL 按 `dnd5e` 处理。

#### Scenario: 调查员卡
- **WHEN** 准备的是 COC 卡（药剂师，28 岁）
- **THEN** 名单显示「桐島 英二（药剂师 · 28岁）」

#### Scenario: 调查员卡没填职业
- **WHEN** 卡的职业为空
- **THEN** 显示「（无职业）」

#### Scenario: DND 卡
- **WHEN** 准备的是 3 级人类战士
- **THEN** 显示「（人类 战士 Lv.3）」

#### Scenario: 旧快照
- **WHEN** `pending.json` 里的快照是 1.63 之前的格式（无 rules、无种族职业）
- **THEN** 只显示角色名，不出现「? ? Lv.1」
