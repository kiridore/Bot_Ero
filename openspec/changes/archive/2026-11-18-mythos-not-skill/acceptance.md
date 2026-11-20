# 克苏鲁神话不是技能 — 验收记录

实施分支：`master`；版本 2.3.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 不在技能表 | `test_trpg_coc.py::test_mythos_is_not_a_skill`（`default_skill_names` / `skill_base_map` 都不含） | 通过 |
| AC02 不渲染旧行 | 同上：`finalize` 的 skills 不含，`max_san` 仍按背景字段（12 → 87） | 通过 |
| AC03 `.ra` 仍可用 | `test_mythos_roll_reads_background_field`（23） | 通过 |
| AC04 旧卡迁移 | `test_legacy_mythos_row_folds_into_background`（5 + 兴趣 18 → 18，行删除） | 通过 |
| AC05 播种数量 | `check_trpg_coc_api.py`：`default_skills` 38 项、「克苏鲁神话不在技能表里」 | 通过 |
| AC06 页面 | 13 个 COC JS 用例 + 查看页 DOM 全过 | 通过 |
| AC07 全量回归 | `python -m pytest -q` → **1047 passed**（5:40） | 通过 |
| AC08 文档与归档 | `openspec validate coc-character-sheet --strict` valid；`CHANGELOG [2.3.0]` 与 `BOTERO_VERSION = "2.3.0"` 一致；同一 commit 归档 | 通过 |

## 行为对照

| 位置 | 修前 | 修后 |
|---|---|---|
| 标准技能表 | 39 项（含克苏鲁神话 0%） | 38 项 |
| 建卡页技能表 | 有「克苏鲁神话」行，可填兴趣点 | 无该行，数值在背景区输入框 |
| 查看页 | 在「资产」行末尾显示 | 「背景」区块显示「克苏鲁神话：N」 |
| `.ra 克苏鲁神话` | 读技能行 | 读 `cthulhu_mythos`（行为不变） |
| 旧卡技能行 | 一直显示并可加点 | 打开/保存时并入背景字段后删除 |

## 说明

- `growth.NO_GROWTH_SKILLS` 仍保留「克苏鲁神话」，用于兜住旧卡残留行的一次性清理，不影响新卡。
- `skill_notes` 里那条神话说明保留（查看旧卡或未来做「背景说明」时可复用）。
