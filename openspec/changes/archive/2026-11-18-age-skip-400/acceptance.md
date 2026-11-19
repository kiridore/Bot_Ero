# 「不再提示」不折叠 — 验收记录

实施分支：`master`；版本 2.1.3。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 空卡也能跳过 | `test_trpg_coc_age.py::TestAgeAdjustOnIncompleteCard::test_skip_works_when_card_incomplete` | 通过 |
| AC02 空卡也能应用 | 同文件 `test_apply_works_when_card_incomplete`（力量 55→50、外貌 50→45） | 通过 |
| AC03 证明旧行为会拦 | 同文件 `test_full_validation_would_have_blocked`（`validate()` 报信用评级） | 通过 |
| AC04 全量回归 | `python -m pytest -q` → **1011 passed**（5:38）；`check_trpg_coc_api.py` 全过 | 通过 |
| AC05 文档与归档 | `openspec validate coc-character-sheet --strict` valid；`CHANGELOG [2.1.3]` 与 `BOTERO_VERSION = "2.1.3"` 一致；同一 commit 归档 | 通过 |

## 复现（修前）

```
POST /api/me/characters/5/age-adjust  {"action": "skip"}
→ 400 信用评级应在 20-50 之间（当前 0）
```

前端 `sendAgeAdjust()` 因此抛错 → `afterAgeAdjust()` 不执行 → `card.age_adjust` 仍是旧值 → `renderAgeAdjust()` 继续渲染展开态。

## 修后

```
POST .../age-adjust {"action": "skip"}
→ 200 {"age_adjust": {"kind": "skipped", "age": 45, "band": "40-49"}, ...}
→ afterAgeAdjust → ageSkipOpen = false → renderAgeAdjust() → 折叠
```

## 校验范围对照

| 校验 | age-adjust 接口 | 正常保存 |
|---|---|---|
| 年龄 15–99、记录与年龄一致、体能分配、属性扣后 ≥1 | ✅ 拦 | ✅ 拦 |
| 信用评级区间、可选池、点数预算、非本职技能加点 | ❌ 不拦 | ✅ 拦 |
