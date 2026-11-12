# 选职业自动补本职技能 — 验收记录

实施分支：`master`；版本 1.76.2。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 固定项过滤 | `test_trpg_coc_skill_name.js`：`requiredSkillNames` 保留「会计」「科学:化学」，剔除 `技艺:*`；无职业返回 `[]` | 通过 |
| AC02 自动补行 | `test_trpg_coc_occupation_fill.js`：药剂师固定项 4 条 → 补入 3 行（跳过通配），重复调用返回 0 | 通过 |
| AC03 换职业清理 | 同上：填过兴趣点的「会计」保留；其余自动行被 `pruneAutoAdded` 移除；改选后补入新职业技能 | 通过 |
| AC04 接线 | `test_trpg_coc.py::test_occupation_fills_required_skills`：切换回调含 `pruneAutoAdded();` 与 `const added = fillRequiredSkills(occ);` | 通过 |
| AC05 文档与归档 | 全量 `pytest` → **755 passed**（4:44）；`openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.76.2]` 与 `BOTERO_VERSION = "1.76.2"` 一致 | 通过 |

## 实测与裁定

- **根因**：1.73 只处理了 `choices`（可选池），`required`（固定本职技能）从未进入技能表；职业定义里这部分信息是现成的，属于实现缺口而非设计取舍。
- **通配项处理**：81 条 `类别:*` 固定项无法自动补（专攻由玩家定），保持不补并依赖「添加技能」或可选池机制。
- **不误删输入**：`pruneAutoAdded` 只撤「自动补入且三列点数全为 0」的行，填过点数的一律保留。
- **不加自动触发**：只在 `change` 事件触发，避免打开已有卡时把玩家删掉的行重新加回。
