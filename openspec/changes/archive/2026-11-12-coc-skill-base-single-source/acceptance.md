# 技能基础值单一来源 — 验收记录

实施分支：`master`；版本 1.80.3。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 统一表 | `TestSkillBaseConsistency::test_map_covers_three_kinds`：106 项，含会计 5 / 科学:化学 1 / 斗殴 25 | 通过 |
| AC02 三路径一致 | `test_finalize_uses_same_table`（会计、科学:化学、技艺:表演、斗殴、手枪）与 `test_growth_mark_uses_same_table`（专攻 2 项 + 斗殴）逐一比对统一表 | 通过 |
| AC03 播种范围 | `test_default_skills_are_standard_only`：恰 39 项、不含科学:化学/斗殴；API 断言 `default_skills` 39 项 | 通过 |
| AC04 前端查值 | `test_trpg_coc_skill_defaults.js`「只铺标准技能」；`test_trpg_coc_occupation_fill.js` 补行改走 `skillBaseFor` | 通过 |
| AC05 闪避不受影响 | `test_dodge_still_derived`：`skill_defaults(55)["闪避"] == 27` | 通过 |
| AC06 文档与归档 | 全量 `pytest` → **818 passed**（5:10）；`openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.80.3]` 与 `BOTERO_VERSION = "1.80.3"` 一致 | 通过 |

## 实测与裁定

- **修复前的实测差异**：`科学:化学` 存空行时 base=0、缺行时无默认、mark 补行 base=1；`斗殴` 同理 0 / 无 / 25；只有标准技能三处一致（会计 5）。
- **四张表合一**：`SKILL_BASE`（39）+ `SKILL_NOTES`（附表 110）+ `weapon_skill_base()`（19）在 `skill_base_map()` 里合并（译名统一 canonical），前端不再只看 39 项。
- **播种与兜底分层**：`default_skill_names()` 明确只有 39 项进技能表；`finalize` 的读时补全也仍是 39 项——统一的是「数值来源」，不是「铺多少行」。
- **顺带修好**：武器库选武器时成功率按 `skillBaseFor(使用技能)` 取（以前恒 0），职业自动补入/可选池补行同理。
- **未做**：`母语`（= EDU）仍不参与基础值表；附表里的「学识：」「生存：」等带冒号结尾的键未规范化。
