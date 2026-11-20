# `.幸运` 指令 — 验收记录

实施分支：`master`；版本 2.2.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 减少 | `TestLuck::test_spend` | 通过 |
| AC02 增加 | `test_gain` | 通过 |
| AC03 英文别名 | `test_english_alias` | 通过 |
| AC04 骰子 | `test_dice_expression`（`-d6=3`） | 通过 |
| AC05 下限 | `test_floor_zero` | 通过 |
| AC06 上限 | `test_cap_99` | 通过 |
| AC07 格式 | `test_requires_sign`、`test_missing_value` | 通过 |
| AC08 规则门控 | `test_dnd_card_refused` | 通过 |
| AC09 权限 | `test_other_target_needs_dm`、`test_dm_can_target_others` | 通过 |
| AC10 全量回归 | `python -m pytest -q` → **1044 passed**（5:41） | 通过 |
| AC11 文档与归档 | `openspec validate trpg-vitals --strict` valid；菜单与 `kb/DICE_GUIDE.md` 已加；`CHANGELOG [2.2.0]` 与 `BOTERO_VERSION = "2.2.0"` 一致；同一 commit 归档 | 通过 |

## 实测回执

```
.幸运 -10   → 老张的幸运 45 → 35（-10）
.幸运 -1d6  → 老张的幸运 30 → 27（-d6=3）
.幸运 -50   → 老张的幸运 27 → 0（-50）
              · 幸运已见底（不会低于 0）
.幸运 +50   → 老张的幸运 90 → 99（+50）
              · 幸运上限 99，多出的部分不计
```

## 未做（明确不在本轮范围）

- 其它属性（力量/敏捷/教育等）的增减：会连带 HP/MP/MOV/伤害加值、职业点与兴趣点预算，以及与 `age_adjust.applied` 记录的一致性校验（实测直接改属性会让下一次保存 400），需要单独设计。
- 幸运的「花费日志」与撤销：与 `.ti` 一致，不做历史记录。
