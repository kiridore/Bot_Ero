# 非本职技能行禁用职业点列 — 验收记录

实施分支：`master`；版本 1.73.2。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 允许集合 | `node test/test_trpg_coc_skill_name.js`：新增 6 项断言全过（固定项、`技艺:*` 通配、已选池内技能可加点；未选中的自由技能不可；别名按规范名匹配；无职业时集合为空） | 通过 |
| AC02 行禁用 | `test_trpg_coc.py::test_non_occ_rows_disable_occ_column` 通过：源码含 `occInput.disabled = !allowed`、`is-not-occ`，CSS 含 `[data-occ]:disabled` | 通过 |
| AC03 视觉 | 药剂师卡中「攀爬」行职业列 `disabled` + `is-not-occ` 淡灰；兴趣列不受影响；选中后 `occAllows` 命中即解禁 | 代码层通过，视觉待确认 |
| AC04 文档与归档 | 全量 `pytest` → **722 passed**（4:46）；`openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.73.2]` 与 `BOTERO_VERSION = "1.73.2"` 一致 | 通过 |

## 实测与裁定

- **根因**：1.72/1.73 只做了服务端校验，页面把职业列渲染在每一行且始终可编辑，玩家要保存后才知道错；一次只报一条，改完再存再报。
- **清零策略**：只在「行变为不可加点且有数值」时清零并提示，避免留下必然 400 的死数据；未涉及的行保持原值。
- **纯函数化**：`occAllowedNames`/`occAllows` 放在 `escapeHtml` 之前，测试直接从源码截取执行，规则不会与页面漂移。
- **服务端仍是最终裁决**：页面禁用只是提前拦住，绕过页面直接调接口依然 400。
