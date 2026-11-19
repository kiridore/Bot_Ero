# 职业点：本职属性可选 + 自定义职业第二属性

## Why

COC 7th 有一批职业的技能点公式写成「教育×2＋力量或敏捷×2」这种二选一形式（猎人、运动员、赏金猎人、海员等 20 余个）。当前实现一律取高（与新卡 F 列的 `MAX()` 一致），玩家无法表达「我这个角色用的是力量」，预算被静默拉高到最优解。另外 `自定义职业` 在新卡里叫玩家填「第二职业属性」（外貌/意志/教育/敏捷/力量/体质/体型，留空视为教育），我们完全没有这个入口，公式写死 `教育×4`。

顺带查出的真实数据错误：

| 职业 | 新卡公式 | 我们（修前） | 结果 |
|---|---|---|---|
| 海员-军舰海员 | 教育×2＋敏捷或力量×2 | 教育×4 | 教育 80 时 300 vs 320 |
| 海员-民船海员 | 教育×2＋敏捷或力量×2 | 教育×4 | 同上 |

## What Changes

- 新增卡片字段 `occupation_attr`（本职属性）：带「或」的职业可指定其中一项；`自定义职业` 用它表示第二职业属性。
- `points_budget(formula, data, chosen)`：带「或」的项按 `chosen` 取值，未指定则取高（保持旧行为）。
- `occupation_budget(data)`：自定义职业按新卡口径 `教育×2＋第二属性×2`，留空 = `教育×4`。
- `occupation_attr_problems(data)`：属性必须是该职业公式里的候选项（自定义职业为八属性之一）；无「或」的职业不允许填。
- `finalize` 输出 `occupation_attr` 与按选择计算的 `occupation_budget`；`validate` 接上校验；`format_sheet`（`/跑团 角色 查看`）输出职业点与所选属性。
- 建卡页：职业区下方出现单选项（带「或」的职业为「不指定（取高）/ 力量 / 敏捷」，自定义职业为「留空（视为教育）+ 八属性」）；预算实时按选择刷新；换职业清空选择。
- 查看页：职业点行显示「（按力量）」。
- 职业数据对齐新卡（CY26.3 职业列表首个同名行）：24 条公式文本统一为「教育×2＋力量或敏捷×2」写法，其中 2 条（两条海员）是真实数值修正。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：职业点预算的口径与选择入口。

## Scope and Compatibility

- 未填写 `occupation_attr` 的旧卡行为完全不变（取高）。
- 新卡职业列表里 6 个职业名重复（艺术家/工匠/艺人/律师/私家侦探/科学家），后一组用新版技能译名（艺术及手艺、其他语言）。我们的技能体系基于前一组，本次按**首个同名行**对齐，不引入后一组（记为已知差异）。
- 无数据库变更；版本 2.1.0。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 公式候选项 | `python -m pytest test/test_trpg_coc_occ_attr.py -q -k FormulaOptions` | `教育×2＋力量或敏捷×2` → `[力量, 敏捷]`；`教育×4` → `[]` |
| AC02 默认取高 | `... -k default_takes_higher` | 猎人 EDU80 STR45 DEX70 → 300 |
| AC03 按选择算 | `... -k chosen_lower_attribute` | 同上卡按力量 → 250 |
| AC04 自定义职业 | `... -k custom_occupation` | 留空 320；第二属性意志（POW65）→ 290 |
| AC05 校验 | `... -k AttrProblems` | 猎人填「意志」被拒；会计师填任何属性被拒；自定义职业八属性均可；无职业填属性被拒 |
| AC06 数据修正 | `... -k OccupationData` | 两条海员公式为 `教育×2＋敏捷或力量×2`，预算 300（不是 320） |
| AC07 落库与回传 | `python test/scripts/check_trpg_coc_api.py` | 按力量/敏捷分别得到 210/200；非法 400；自定义职业留空 180、意志 220；无「或」填属性 400 |
| AC08 页面选择器 | `node test/test_trpg_coc_occ_attr.js` | 猎人 3 个单选项、自定义职业 9 个、会计师不显示；非法残留值被清空；选中后预算按选择变化 |
| AC09 全量回归 | `python -m pytest -q` | 全绿 |
| AC10 文档与归档 | `openspec validate coc-character-sheet --strict`；归档与实现同一 commit | `CHANGELOG [2.1.0]` 与 `BOTERO_VERSION` 一致 |
