# 动态基础值 — 验收记录

实施分支：`master`；版本 1.80.4。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 动态派生 | `TestDynamicBases::test_dynamic_table`：闪避 27（DEX 55）、母语 70（EDU 70）、会计 5 | 通过 |
| AC02 finalize 忽略存储值 | `test_finalize_derives_and_ignores_stored`：卡上写 `闪避 base 0 / 母语 base 5`，DEX 80 / EDU 45 → 40 / 45 | 通过 |
| AC03 成长补行 | `test_growth_mark_uses_dynamic_value`：`mark("母语")` 补出 base 80（EDU 80） | 通过 |
| AC04 默认补全 | `test_skill_defaults_include_mother_tongue`：闪避 27、母语 70；`test_finalize_includes_all_standard_skills` 断言 39+1 项 | 通过 |
| AC05 键规范化 | `test_trailing_colon_notes_normalized`：表内无「学识：/生存：」，有「学识」1 与「生存」10；`test_notes_index_handles_colon_keys` 说明索引仍保留原名 | 通过 |
| AC06 前端 | `test_trpg_coc_skill_defaults.js`：母语随教育 70、闪避随敏捷 27；无属性输入时为 0 | 通过 |
| AC07 文档与归档 | 全量 `pytest` → **824 passed**（5:08）；`openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.80.4]` 与 `BOTERO_VERSION = "1.80.4"` 一致 | 通过 |

## 实测与裁定

- **为什么是「动态」而不是「往表里加数字」**：闪避与母语的基础值完全由属性决定，写成固定数字会在属性变化后立刻过期（这正是之前 `闪避 base 0` 的老问题）。
- **规则集中在 `DYNAMIC_BASES`**：`{闪避: 敏捷÷2, 母语: 教育}`，Python 侧 `dynamic_skill_base()`、前端按 options 下发的 `dynamic_bases` 各读同一份规则，避免两端各写一遍公式。
- **覆盖语义**：卡上存的闪避/母语基础值一律被派生值覆盖（延用闪避原有规则），其他技能仍是「卡上值优先」。
- **键规范化只影响基础值表**：技能说明索引保留「学识：」原键，按原名仍能看到说明。
- **计数变化**：`finalize` 输出从 39 项变 40 项（多母语），一条旧断言相应从 `len(SKILL_BASE)` 改为 `+1`。
- **未做**：「生存：」的专攻（生存:沙漠等）仍按类别前缀匹配、基础值取 10；`学识` 的专攻同理取 1。
