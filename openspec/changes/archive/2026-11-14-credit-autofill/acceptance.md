# 信用评级自动填充 — 验收记录

实施分支：`master`；版本 1.96.2。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 补下限 | `node test/test_trpg_coc_credit_fill.js`：「选职业把信用评级补到下限 35」「资产区同步为下限 35」「合计列同步 35」 | 通过 |
| AC02 不覆盖 | 「已有加点不被覆盖 40」 | 通过 |
| AC03 旧卡迁移 | 「旧卡迁移：下限部分记职业点 35」「超出部分记兴趣点 10」「迁移后资产区仍是 45」 | 通过 |
| AC04 无职业 | 「无职业时旧值记兴趣点 0/20」 | 通过 |
| AC05 不重复迁移 | 「已有加点时不重复迁移 0」 | 通过 |
| AC06 接线 | 「职业变更先补下限」「职业没变但补了下限会刷新派生」「加载完成后迁移旧值并补下限」；`TestOccupationSearch` 守卫改为「`fillCreditFloor(occ)` 出现在早退之前」 | 通过 |
| AC07 全量回归 | `python -m pytest -q` → **949 passed**（5:13）；DOM 套件 31 项全过（新用例自动纳入） | 通过 |
| AC08 文档与归档 | `openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.96.2]` 与 `BOTERO_VERSION = "1.96.2"` 一致；同一 commit 归档 | 通过 |

## 三处根因

1. `lastOccupation` 在 `bind()` 时就被初始化成当前职业名，重复选同一职业 → `occ.name === lastOccupation` 早退，补下限不执行。
2. 1.94.0 之前信用评级只存在 `credit_rating` 字段；服务端只在保存时迁移，打开旧卡时页面显示技能行 0、资产区 0。
3. 极旧卡技能表没有「信用评级」行，`creditRowEl()` 返回 undefined，填充被静默跳过。

## 修复方式

- 新增 `ensureCreditRow()`（缺行先补）、`fillCreditFloor(occ)`（合计 0 时填下限）、`seedCreditFromAsset()`（旧值迁移），三者都幂等。
- 职业变更处理器先补下限、再判断职业是否变化；补到了就刷新派生值。
- `init()` 在 `render()` 之后调用迁移与补下限，打开即有值。
- 前端只做预填，不写库；保存时服务端 `normalize_credit_rating()` 仍按同一口径归一化。
