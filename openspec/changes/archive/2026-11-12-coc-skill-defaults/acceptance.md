# 技能默认值与职业可选 — 验收记录

实施分支：`master`；版本 1.79.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 默认值表 | `test_trpg_coc.py::TestSkillDefaults::test_skill_defaults_table`：会计 5、侦察 25、急救 30、闪避 27（DEX 55）；`test_unknown_skill_still_missing` 飞天 仍为 None | 通过 |
| AC02 读时兜底 | `test_finalize_includes_all_standard_skills`：`skills={}` 时技能数 = `len(SKILL_BASE)`（39）、急救 total=30；`test_stored_skill_overrides_default`：基础 30 + 兴趣 10 → 40 | 通过 |
| AC03 闪避口径 | `test_dodge_uses_dex_not_stored_base`：卡上写 base 0 → 仍 27；DEX 80 → 40 | 通过 |
| AC04 无职业建卡 | `test_validate_allows_missing_occupation`（无问题）、`test_validate_rejects_occupation_points_without_occupation`；API 脚本「未选职业可保存 200」「无职业不能加职业点 400」 | 通过 |
| AC05 页面默认技能 | `node test/test_trpg_coc_skill_defaults.js`：9 项断言全过（覆盖整表、闪避按敏捷、已存点数保留、表外技能保留、缺省敏捷为 0） | 通过 |
| AC06 接口 | `check_trpg_coc_api.py`「默认技能进接口」：查看接口 ≥39 项技能、急救 30、闪避 = 55//2 = 27 | 通过 |
| AC07 文档与归档 | 全量 `pytest` → **776 passed**（4:49）；`openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.79.0]` 与 `BOTERO_VERSION = "1.79.0"` 一致 | 通过 |

## 实测与裁定

- **读时兜底而非写盘迁移**：默认值由 `finalize()` 补，老卡无需迁移即可在查看页/`.ra` 里获得全部技能；建卡页加载时合并默认值，首次保存后卡片自带完整技能表。
- **闪避是不可覆盖的派生值**：卡上写的闪避 base 一律忽略，避免「敏捷 55 但闪避 0」这种自相矛盾的卡；提升途径仍是成长/职业/兴趣点三列。
- **受影响的旧用例**（3 处，均已修正）：`test_validate_requires_occupation` 改为「允许无职业」；`skill_value("驾驶")` 由 None 变为默认值 20（汽车驾驶）；`.ra 驾驶` 的「技能不存在」用例改用真正不存在的「飞天」。
- **未做**：武器技能（斗殴/手枪/射击:步枪 等）仍不在 39 项标准技能内，不会因本变更凭空出现；`.ra 斗殴` 依旧要求卡上有该技能行（`.atk` 未实现，属既有范围）。
