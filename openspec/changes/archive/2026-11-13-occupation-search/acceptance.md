# 职业可搜索 — 验收记录

实施分支：`master`；版本 1.96.1。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 控件 | `TestOccupationSearch::test_input_with_datalist`：含 `id="occupation"`、`list="occOptions"`、`<datalist id="occOptions">`，不含 `<select id="occupation">` | 通过 |
| AC02 精确匹配 | `test_exact_match_only`：`unknownOccupation` + `o.name === name` | 通过 |
| AC03 保存拦截 | `test_save_blocks_unknown`：保存前调用并提示「不在列表里」 | 通过 |
| AC04 只在真换职业时重置 | `test_switch_only_on_real_change`：`if (occ.name === lastOccupation) return;` | 通过 |
| AC05 全量回归 | `python -m pytest -q` → **948 passed**（5:11）；10 个 COC JS 套件全过；`check_trpg_coc_api.py` 全过 | 通过 |
| AC06 文档与归档 | `openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.96.1]` 与 `BOTERO_VERSION = "1.96.1"` 一致；同一 commit 归档 | 通过 |

## 行为对照

| 操作 | 以前 | 现在 |
|---|---|---|
| 点颜色区/箭头 | 展开 113 项长列表 | 展开候选（可继续打字过滤） |
| 输入「潜水」 | 无法输入 | 候选筛出「潜水员」，选中即生效 |
| 输入半个名字直接保存 | 不适用（无输入框） | 拒绝并提示 |
| 重新选中当前职业 | 清空可选池 + 重补本职技能 | 不动（避免误清） |

## 说明

- 用浏览器原生 `input + datalist`：零额外 JS、可访问性由浏览器负责；代价是候选样式不可定制（不同浏览器外观不同），Safari 的候选可能要先输入才显示。
- 职业名的唯一来源仍是 `/api/trpg/coc/options` 下发的 `occupations`，前端不再有第二份名单。
- 判定「真换职业」用 `lastOccupation` 记录上一次匹配成功的职业名，空值等于「未选择」。
