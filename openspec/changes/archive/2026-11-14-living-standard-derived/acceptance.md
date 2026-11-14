# 生活水平由信用评级推算 — 验收记录

实施分支：`master`；版本 1.97.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 跟随信用评级 | `TestLivingStandardDerived::test_follows_credit`：35/40 → 标准，50/60 → 小康，卡上原值「富豪」被纠正 | 通过 |
| AC02 信用 0 | `test_zero_credit`：无职业、无加点 → 身无分文 | 通过 |
| AC03 脏值 | `test_unknown_level_still_rejected`：`贫穷` → 报「不在 6 档」且值不被改写 | 通过 |
| AC04 页面 | `test_page_is_output`：含 `<output id="living_standard"`、不含 `<select id="living_standard"`、`collect` 提交推算值 | 通过 |
| AC05 接口回归 | `check_trpg_coc_api.py` 全部通过（含「非法生活水平 400」） | 通过 |
| AC06 全量回归 | `python -m pytest -q` → **953 passed**（5:14）；10 个 COC JS 套件全过 | 通过 |
| AC07 文档与归档 | `openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.97.0]` 与 `BOTERO_VERSION = "1.97.0"` 一致；同一 commit 归档 | 通过 |

## 档位来源（`core/trpg/asset_data.py::LEVELS`，取自 xlsx「资产及物价参考」）

| 信用评级 | 生活水平 |
|---|---|
| 0 | 身无分文 |
| 1–9 | 拮据 |
| 10–49 | 标准 |
| 50–89 | 小康 |
| 90–98 | 富裕 |
| 99 | 富豪 |

## 说明

- 归一化只纠正「6 档之内但和信用评级不一致」的值；不在 6 档里的脏值保持原样交给 `asset_problems()` 报 400，避免把错误数据悄悄改成合法值。
- 「按规则填入」仍按币种 + 信用评级查现金 / 其他资产 / 消费水平，只是不再写生活水平那一格。
