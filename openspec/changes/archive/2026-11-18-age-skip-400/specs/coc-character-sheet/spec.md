# coc-character-sheet — 变更（年龄调整接口的校验范围）

## ADDED Requirements

### Requirement: 年龄调整不要求整张卡已经合规
`POST /api/me/characters/{id}/age-adjust` MUST 只在年龄相关约束不满足时拒绝：年龄不在 15–99、`age_adjust.age` 与卡片年龄不一致、体能分配与年龄段不符、扣减后属性低于 1。信用评级区间、可选池、职业点预算等整卡合规问题 MUST NOT 阻止「应用年龄调整」与「不再提示」。

#### Scenario: 卡还没填完时跳过
- **WHEN** 45 岁的卡信用评级仍为 0（低于职业下限），玩家点「不再提示」
- **THEN** 接口返回 200 并写入 `{"kind":"skipped","age":45,"band":"40-49"}`，面板折叠

#### Scenario: 卡还没填完时应用
- **WHEN** 同一张卡填好体能分配后点「应用年龄调整」
- **THEN** 属性按年龄段调整成功，与信用评级无关
