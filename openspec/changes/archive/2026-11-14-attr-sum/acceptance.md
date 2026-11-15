# 属性合计（不含幸运） — 验收记录

实施分支：`master`；版本 1.98.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 编辑页 | `test_trpg_coc.py::test_attr_sum_excludes_luck`：源码含 `id="out-attr-sum"`、`属性合计（不含幸运）`、`.filter(([key]) => key !== "luck")` | 通过 |
| AC02 查看页 | `node test/test_trpg_coc_view_dom.js`：「属性合计（不含幸运）」且数值 470（60+55+45+55+60+85+65+45） | 通过 |
| AC03 不含幸运 | 样例卡含幸运为 520，页面显示 470 | 通过 |
| AC04 全量回归 | `python -m pytest -q` → **954 passed**（5:15）；10 个 COC JS 套件全过 | 通过 |
| AC05 文档与归档 | `openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.98.0]` 与 `BOTERO_VERSION = "1.98.0"` 一致；同一 commit 归档 | 通过 |

## 口径

| 项 | 是否计入 |
|---|---|
| 力量 / 体质 / 体型 / 敏捷 / 外貌 / 智力 / 意志 / 教育 | 计入 |
| 幸运 | **不计入** |

数值取当前卡片的属性值（含年龄调整的结果），与界面上显示的数字一致；不参与 HP/SAN/职业点等任何派生计算。
