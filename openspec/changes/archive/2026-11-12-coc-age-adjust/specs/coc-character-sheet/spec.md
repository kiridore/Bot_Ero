# coc-character-sheet — 变更（年龄调整）

## ADDED Requirements

### Requirement: 年龄调整表与应用
建卡工具 SHALL 按 COC 7th 规则提供年龄调整：15–19 岁 STR 与 SIZ 合计 −5、EDU −5、幸运掷两次取高；20–39 岁 EDU 成长检定 ×1；40–49/50–59/60–69/70–79/80–89 岁 STR/CON/DEX 合计 −5/−10/−20/−40/−80、APP −5/−10/−15/−20/−25、EDU 成长检定 ×2/×3/×4/×4/×4；MOV 为 `max(0, age // 10 - 3)`。体能（或 STR/SIZ）的合计扣减 SHALL 由玩家分配，MUST NOT 由系统指派。EDU 成长检定 MUST 由服务器掷（1D100 > 当前 EDU 时 +1D10，上限 99），结果写入卡片 `age_adjust.edu.rolls`。

#### Scenario: 应用 45 岁调整
- **WHEN** 玩家在 45 岁的卡上填入力量 −3、体质 −2、敏捷 0 并点击「应用年龄调整」
- **THEN** 三项属性按分配扣减、APP −5、EDU 按两次成长检定结果增加、`age_adjust` 记录最小值与掷骰明细，HP/伤害加值/闪避/MOV 随之重算

#### Scenario: 分配不合规
- **WHEN** 体能分配之和为 −3（额度为 −5）
- **THEN** 接口返回 400，提示「体能合计应扣 5 点，当前为 3 点」，卡片不变

#### Scenario: 年龄改动后应用记录过期
- **WHEN** 卡上 `age_adjust.age` 为 45 而 `age` 被改成 50 并保存
- **THEN** 拒绝保存并提示重新应用或撤销

#### Scenario: 撤销
- **WHEN** 调用 `DELETE /api/me/characters/{id}/age-adjust`
- **THEN** 属性与 EDU 还原为调整前数值，`age_adjust` 被移除

#### Scenario: 未处理的老卡
- **WHEN** 卡片不含 `age_adjust`
- **THEN** 属性与派生值保持原样，可正常保存，页面提供「应用」与「不再提示」两个操作

#### Scenario: MOV 边界
- **WHEN** 年龄为 39、40、50、80、90
- **THEN** MOV 减值分别为 0、1、2、5、6
