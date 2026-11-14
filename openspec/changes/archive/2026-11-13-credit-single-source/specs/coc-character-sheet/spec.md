# coc-character-sheet — 变更（信用评级单一来源）

## ADDED Requirements

### Requirement: 信用评级以资产区为唯一来源
信用评级 SHALL 只以卡上的 `credit_rating`（资产区）为真实值。`finalize()` MUST 把技能表的「信用评级」行渲染为镜像：`total` 等于 `credit_rating`（钳 0–99），技能行上的 `growth`/`occupation`/`interest` MUST NOT 参与计算。`skill_value("信用评级")` 与 `.ra 信用评级` MUST 返回该值；未写下该技能行时同样可查。`.ra 信用评级` 的结果 MUST 不产生成长标记。

#### Scenario: 技能行残留点数
- **WHEN** 卡上资产区为 45、技能表「信用评级」写着兴趣点 20
- **THEN** 角色卡查看、`.ra 信用评级` 都用 45

#### Scenario: 没有该技能行
- **WHEN** 卡上技能表没有「信用评级」行
- **THEN** `.ra 信用评级` 仍按资产区数值检定

### Requirement: 旧卡点数并入资产区
保存时 SHALL 归一化：若技能表的「信用评级」行带成长/职业/兴趣点，且资产区 `credit_rating` 为 0，则把这些点数并入 `credit_rating`；随后把这三列清零。资产区已有值时不覆盖，只清零点数。

#### Scenario: 资产区为空
- **WHEN** 技能行兴趣点 40、资产区 0
- **THEN** 保存后资产区为 40，技能行点数清零

#### Scenario: 资产区已有值
- **WHEN** 技能行兴趣点 40、资产区 45
- **THEN** 保存后资产区仍为 45，技能行点数清零

### Requirement: 建卡页信用评级只读
建卡页技能表的「信用评级」行 MUST 四列只读并提示在资产区填写；资产区数值变化 SHALL 即时同步到该行；保存时该行 MUST 提交全 0。

#### Scenario: 改资产区
- **WHEN** 玩家在资产区把信用评级改成 60
- **THEN** 技能表对应行显示 60，且该行不可编辑
