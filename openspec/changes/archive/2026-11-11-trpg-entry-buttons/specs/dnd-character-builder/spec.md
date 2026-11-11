# dnd-character-builder — 变更（建卡入口）

## ADDED Requirements

### Requirement: 建卡入口排列
列表页（`/trpg`）SHALL 在标题右侧以同一容器承载两个建卡入口：`新建 DND 5E 卡` 与 `新建 COC 7th 卡`。两者 SHALL 使用相同的按钮样式（不存在主次配色差异），间距一致、右对齐，容器在窄屏可换行；「新建 DND 5E 卡」SHALL 排在前面。空状态提示 SHALL 同时指出两个入口。

#### Scenario: 列表页标题行
- **WHEN** 用户打开 `/trpg`
- **THEN** 标题「我的角色卡」右侧并排出现两个同色按钮，DND 在前

#### Scenario: 窄屏
- **WHEN** 视口宽度不足
- **THEN** 两个按钮换行显示且不重叠
