# 信用评级由技能点决定 — 验收记录

实施分支：`master`；版本 1.94.0（取代 1.93.0 的「资产区唯一来源」）。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 职业点 | `TestCreditSkillSource::test_occupation_points_count`：职业 40 → 校验通过、`skill_value` 40、`credit_rating` 40 | 通过 |
| AC02 兴趣点在上限内 | `test_interest_after_floor`：35 + 10 → 45 | 通过 |
| AC03 下限前禁止兴趣点 | `test_interest_before_floor_refused`：仅兴趣 40、职业 30 + 兴趣 5 都报「只能用职业点」 | 通过 |
| AC04 区间 | `test_range_enforced`：职业 20 与 35+50 都报「信用评级应在 35-75 之间」 | 通过 |
| AC05 旧卡迁移 | `test_legacy_asset_value_migrates`：资产 45 → 职业 35 + 兴趣 10，`credit_rating` 45 | 通过 |
| AC06 基础与成长 | `test_base_and_growth_ignored`：base 30 / growth 5 归零，成长并入职业点 | 通过 |
| AC07 职业点不拒 | `test_occupation_points_allowed_for_credit` | 通过 |
| AC08 骰子 | `test_ra_credit_uses_skill_points`：`[信用评级=40]` 且不打勾 | 通过 |
| AC09 接口 | `check_trpg_coc_api.py`：职业点建卡 200 + 资产同步；35+10 → 45；仅兴趣 400；超上限 400；旧卡迁移 | 通过 |
| AC10 页面 | `TestCreditSkillUi` 3 例 + 10 个 COC JS 套件全过；`syncCreditAssets()` 在 `render()` 末尾调用 | 通过 |
| AC11 全量回归 | `python -m pytest -q` → **937 passed**（5:10） | 通过 |
| AC12 文档与归档 | `openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.94.0]` 与 `BOTERO_VERSION = "1.94.0"` 一致；同一 commit 归档 | 通过 |

## 加点流程（药剂师，信用评级 35–75）

```
1. 选职业 → 技能行「信用评级」的职业点自动填 35（下限）
2. 想更高：点「按规则填入」前先在技能行兴趣点加数（上限 75）
3. 资产区的信用评级跟着技能行走，不需要也不能手工填
```

## 说明

- `credit_rating` 字段保留但改为派生：每次保存由技能合计写回，资产参考表 / 生活水平 / 快照 / `.ra` 都读它，因此下游无需改动。
- 迁移只发生在「技能行合计为 0 且资产区有值」时，已按新规则填过点数的卡不会被覆盖。
- 历史数据里的成长点（规则上不该有）并入职业点而不是丢弃。
- 未做：界面不会因为「兴趣点填早了」即时标红，只在保存时由服务端拒绝（与职业点超预算的处理一致）。
