# `.ra` 整数加值 — 验收记录

实施分支：`master`；版本 2.4.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 属性加值 | `TestCocCheckBonus::test_attribute_bonus` | 通过 |
| AC02 属性减值 | `test_attribute_penalty` | 通过 |
| AC03 技能加值 | `test_skill_bonus`、`test_skill_bonus_with_space` | 通过 |
| AC04 数值加值 | `test_number_bonus` | 通过 |
| AC05 成长标记 | `test_bonus_keeps_growth_mark_on_skill`、`test_attribute_bonus_has_no_growth_mark` | 通过 |
| AC06 下限 | `test_bonus_cannot_drop_below_one`（35-40=-5） | 通过 |
| AC07 速写形式 | `test_roll_shorthand_with_bonus`、`test_dark_roll_shorthand_with_bonus` | 通过 |
| AC08 不加值时不变 | `test_plain_forms_unchanged` | 通过 |
| AC09 全量回归 | `python -m pytest -q` → **1058 passed**（5:41） | 通过 |
| AC10 文档与归档 | `openspec validate trpg-dice --strict` valid；`kb/DICE_GUIDE.md` 已补；`CHANGELOG [2.4.0]` 与 `BOTERO_VERSION = "2.4.0"` 一致；同一 commit 归档 | 通过 |

## 实测回执

```
.ra 力量            → [力量=60] → 常规成功
.ra 力量+3          → [力量=60+3=63]
.ra 力量-20         → [力量=60-20=40] → 失败
.ra 侦察+10         → [技能=35+10=45]
.ra 侦察 -10        → [技能=35-10=25]
.ra 60+3            → [技能=60+3=63]
.ra 信用评级+5      → [信用评级=40+5=45]
.ra 侦察-40         → 「侦察」的目标值是 35-40=-5，无法检定（需要 1 以上）
.r c60+10           → [技能=60+10=70]
.rh c60+10          → [技能=60+10=70]（暗骰）
```

## 未做

- 骰子加值（`.ra 侦察+1d6`）：按本轮选择只做整数。需要时可扩展 `_split_bonus` 复用掷骰解析。
- `.rc` 不动（它本来就支持表达式）；`.r` 通用表达式不动。
