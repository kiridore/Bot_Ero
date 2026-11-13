# coc-skill-growth — 变更（可打勾范围）

## ADDED Requirements

### Requirement: 克苏鲁神话与信用评级不打勾
成长标记 SHALL 只发给可成长的技能。`克苏鲁神话` 与 `信用评级` MUST NOT 获得成长标记、MUST NOT 参与幕间成长检定、MUST NOT 计入「有技能达到 90% → 当前 SAN +2D6」的触发条件。已有数据里若带有标记，结算时 SHALL 只清空标记，不产生成长。

#### Scenario: 信用评级检定成功
- **WHEN** 玩家 `.ra 信用评级` 成功（信用评级 95%）
- **THEN** 回执正常显示检定结果，卡上没有 `check` 标记

#### Scenario: 结算时带旧勾
- **WHEN** 卡上 `信用评级` 残留 `check: true` 后执行 `/跑团 成长`
- **THEN** 该项不进入成长明细，`growth` 不变，结算后 `check` 被清空

#### Scenario: 90% 理智奖励
- **WHEN** 玩家只有信用评级 95%、没有其它 90% 以上技能
- **THEN** 结算不给 2D6 理智；若有真实技能达到 90% 仍正常给
