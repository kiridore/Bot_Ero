# coc-character-sheet — 变更（随身物品）

## ADDED Requirements

### Requirement: 随身物品
角色卡 SHALL 记录随身物品列表，每项含状态、部位、名称与背包格数。状态 MUST 为「装备 / 携带 / 背包」之一或空；名称必填、不超过 30 字、不区分大小写不重复；背包格 MUST 为 0–20 的整数或空；整表 MUST NOT 超过 40 行。界面 SHALL 按状态分组展示件数并汇总总格数。`/跑团 角色 查看` SHALL 输出前 6 件与「共 N 件 · M 格」。跑团记录快照 SHALL 记录件数与总格数，MUST NOT 存明细。

#### Scenario: 保存合法物品
- **WHEN** 提交「装备 / 躯干 / 防弹背心 / 2 格」
- **THEN** 保存成功

#### Scenario: 非法状态
- **WHEN** 状态填「乱填」
- **THEN** 返回 400 并提示不在 装备/携带/背包 之内

#### Scenario: 重名
- **WHEN** 两行都叫「手电」（大小写或空格不同也算）
- **THEN** 返回 400 并提示重复添加

#### Scenario: QQ 摘要
- **WHEN** 卡上有 8 件物品共 8 格
- **THEN** `/跑团 角色 查看` 显示前 6 件与「… 共 8 件 · 8 格」

#### Scenario: 记录快照
- **WHEN** 开录时角色卡有 2 件物品共 3 格
- **THEN** 记录的 `sheet_start` 含 `inventory_count=2`、`inventory_slots=3`
