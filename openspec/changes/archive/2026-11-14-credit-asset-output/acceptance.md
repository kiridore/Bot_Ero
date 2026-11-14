# 资产区信用评级只读 — 验收记录

实施分支：`master`；版本 1.96.4。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 只读展示 | `TestCreditSkillUi::test_asset_field_readonly`：含 `<output id="credit_rating"`、不含 `<input id="credit_rating"`；`test_trpg_coc_credit_fill.js`「资产区不是输入框（只读展示）」 | 通过 |
| AC02 同步 | 「资产区同步为下限 35」「先填兴趣点：合计仍按玩家填的 35」「旧卡迁移后资产区仍是 45」（桩改为 `textContent`） | 通过 |
| AC03 无输入监听 | 源码守卫：`<input id="credit_rating"` 不再出现，`getElementById("credit_rating").addEventListener` 已删除 | 通过 |
| AC04 按规则填入 | 源码守卫：`const credit = creditFromSkillRow();` | 通过 |
| AC05 全量回归 | `python -m pytest -q` → **949 passed**（5:13）；10 个 COC JS 套件全过 | 通过 |
| AC06 文档与归档 | `openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.96.4]` 与 `BOTERO_VERSION = "1.96.4"` 一致；同一 commit 归档 | 通过 |

## 顺带修掉的两处

1. 原来的 `change` 监听里引用的是 `life_level`，实际元素叫 `living_standard` —— 即使触发也改不到东西。
2. 生活水平跟随逻辑只剩一处（`syncCreditAssets`），且只在「未选择」时生效，不会再覆盖玩家手选的档位。

## 未做

- 生活水平与信用评级不一致时仍只在下方给提示，不强制改回（1.80.0 定的口径）。
