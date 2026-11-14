# 信用评级单一来源 — 验收记录

实施分支：`master`；版本 1.93.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 展示同源 | `TestCreditSkillMirror::test_finalize_uses_asset_value`：技能行兴趣 20 + 资产 45 → total 45、interest 0 | 通过 |
| AC02 取值同源 | `test_skill_value_matches_asset`（`信用评级` / `信用` 都是 45）、`test_missing_row_still_available`、`test_zero_credit_is_zero` | 通过 |
| AC03 迁移 | `test_validate_migrates_leftover_points`（0 + 兴趣 40 → 40，点数清零）、`test_validate_keeps_asset_value`（45 不被覆盖） | 通过 |
| AC04 上限 | `test_credit_clamped`：资产区 140 → 99 | 通过 |
| AC05 骰子 | `test_ra_credit_uses_asset_value`：`[信用评级=40]`；既有 `test_ra_luck_and_credit`（`信用评级` / `信用` 别名）全过 | 通过 |
| AC06 接口保存 | `check_trpg_coc_api.py`：「资产区信用评级回传 45」「技能表信用评级镜像资产区」「技能行点数并入资产区」「资产区已有值不被技能行覆盖」「技能行点数被清零」 | 通过 |
| AC07 页面只读 | `TestCreditSkillUi` 3 例：`isCreditSkill` + 禁用标记 + `collect` 全 0 + 资产区 `input` 同步 | 通过 |
| AC08 全量回归 | `python -m pytest -q` → **936 passed**（5:13） | 通过 |
| AC09 文档与归档 | `openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.93.0]` 与 `BOTERO_VERSION = "1.93.0"` 一致；同一 commit 归档 | 通过 |

## 修复前后的判定对照（药剂师，资产区 45）

| 卡上数据 | 修复前 `.ra 信用评级` | 修复后 |
|---|---|---|
| 技能行 0 | 45（回落资产区） | 45 |
| 技能行兴趣点 20 | **20**（错） | 45 |
| 技能行职业点 30（本不该有） | **30**（错） | 45，且保存时清零 |

## 说明

- `normalize_credit_rating()` 只并入「成长 + 职业 + 兴趣」三类点数，不动 `base`；资产区已有非零值时只清零点数、不覆盖，避免把玩家填的 45 改成 20。
- 归一化写在 `validate()` 开头，两条保存路径（新建/编辑、年龄调整保存）都会走到。
- 技能表那行仍然保留（技能名列表、说明图标、`.ra 信用评级` 命中路径都依赖它），只是不可编辑、值来自资产区。
- 建卡页改资产区时用 `input` 事件实时同步镜像行，不必等失焦。
