# 负合计与明细 — 验收记录

实施分支：`master`；版本 2.1.6。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 修饰可见 | `test_trpg_vitals.py::test_modifier_shown_in_detail` | 通过 |
| AC02 夹到 0 | `test_negative_total_clamped_to_zero`（-1→0、恰好 0 两种） | 通过 |
| AC03 不回血 | `TestExpressionEdgeCases::test_san_negative_total_does_not_heal` | 通过 |
| AC04 不误扣 | `test_san_positive_negative_total_does_not_hurt` | 通过 |
| AC05 累计不为负 | `test_san_check_loss_never_negative`（今日累计 0） | 通过 |
| AC06 修饰生效 | `test_san_check_modifier_applied`（SAN 50 → 46，`d4+1=4（3+1）`） | 通过 |
| AC07 全量回归 | `python -m pytest -q` → **1033 passed**（5:42） | 通过 |
| AC08 文档与归档 | `openspec validate trpg-vitals --strict` valid；`CHANGELOG [2.1.6]` 与 `BOTERO_VERSION = "2.1.6"` 一致；同一 commit 归档 | 通过 |

## 修前 / 修后对照（d4=1）

| 输入 | 修前 | 修后 |
|---|---|---|
| `.san -1d4-2` | 50 → 51（`-d4=-1`） | 50 → 50（`-d4-2=-1→0（1-2）`） |
| `.san +1d4-3` | 50 → 48（`+d4=-2`） | 50 → 50（`+d4-3=-2→0（1-3）`） |
| `.sc 0/1d4-2` | 今日累计 −1 | 今日累计 0 |
| `.sc 1/1d4+1`（d4=3） | `（d4=4）` | `（d4+1=4（3+1））` |
