# trpg-party-roster — 变更（旧快照展示）

## ADDED Requirements

### Requirement: 旧准备快照的括号展示
准备名单 SHALL 按快照渲染「用户 → 角色名（括号）」。当快照缺少 `rules` 字段时，系统 MUST 用该成员当前角色卡（优先 `char_id`，回落当前卡）补齐 `rules`、`race`、`class_name`、`level`、`occupation`、`age` 后再渲染；取不到角色卡时 MUST 只显示角色名，MUST NOT 报错。快照本身 MUST NOT 被改写。

#### Scenario: 旧快照 + COC 卡
- **WHEN** 名单里有 1.81.1 之前准备的快照，其成员当前卡是 COC 调查员（职业「酒保」、27 岁）
- **THEN** 名单显示 `桐島 英二（酒保 · 27岁）`

#### Scenario: 旧快照 + DND 卡
- **WHEN** 该快照成员当前卡是 DND 5E（人类 战士 3 级）
- **THEN** 名单显示 `（人类 战士 Lv.3）`

#### Scenario: 角色卡已删除
- **WHEN** 快照对应的角色卡已被删除
- **THEN** 名单只显示角色名，没有括号，也不报错
