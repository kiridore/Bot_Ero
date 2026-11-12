# 随身物品（装备 / 背包）— 验收记录

实施分支：`master`；版本 1.81.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 校验 | `test_trpg_coc.py::TestInventory`：合法条目通过；名称必填/去重/状态三态/格数 0–20/最多 40 行全部拒绝并给出具体文案 | 通过 |
| AC02 摘要 | `test_summary_and_sheet`：`inventory_summary` = (2 件, 3 格)，`format_sheet` 含「装备：防弹背心（装备）、急救包（背包）」与「共 2 件 · 3 格」；`test_sheet_truncates_after_six`：8 件显示「… 共 8 件 · 8 格」 | 通过 |
| AC03 接口 | `check_trpg_coc_api.py`：带物品的卡保存 200 且原样回传（状态 `装备`）；非法状态 400「不在 装备/携带/背包」；options 下发 `["装备","携带","背包"]` | 通过 |
| AC04 页面 | `test_trpg_coc_view_dom.js`：查看页输出「装备：防弹背心（躯干／2 格）」「背包：急救包（1 格）」「共 2 件 · 3 格」；建卡页表格 + 添加/删除 + 实时合计（`renderInventoryTotals`，源码守卫已通过 bind 运行时用例） | 代码层通过，视觉待确认 |
| AC05 快照 | `test_trpg_snapshots.py::TestInventorySnapshot`：`inventory_count=2`、`inventory_slots=3`；非数字格数按 0 | 通过 |
| AC06 文档与归档 | 全量 `pytest` → **835 passed**（5:09）；`openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.81.0]` 与 `BOTERO_VERSION = "1.81.0"` 一致 | 通过 |

## 实测与裁定

- **字段形状**：`inventory: [{status, slot, name, slots}]`，空数组表示没有物品；旧卡缺字段按空表处理，不迁移。
- **状态固定三态**（装备 / 携带 / 背包）：跑团语义明确（穿了 / 拿在身上 / 放包里）；部位保持自由文本，因为新卡本身没有枚举（查过 `dataValidation` 与 `definedName`，B/D 列都没有下拉）。
- **背包格只统计不设上限**：规则里容量与体格相关，硬编码上限会与后续战斗/负重规则冲突。
- **记录快照只存件数与格数**：明细属于角色卡，不进 `meta.json`，避免每条记录膨胀。
- **未做**：物品与武器/防具的联动（穿上的防具不自动提供护甲值）、物品重量与负重规则、`.item` 之类的群内指令。
