# 年龄调整折叠与准入 — 验收记录

实施分支：`master`；版本 2.1.1。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 折叠 | `node test/test_trpg_coc_age_dom.js`：「skipped 折叠成一行」「折叠态给重新应用入口」 | 通过 |
| AC02 展开 | 同上：「点重新应用后展开」（含「之前选过「不再提示」」） | 通过 |
| AC03 自动展开 | 同上：「年龄改了以后自动展开」（45 → 55） | 通过 |
| AC04 属性未填 | 同上：「属性为 0 时应用按钮禁用」「属性为 0 时提示先掷属性」；属性补齐后「按钮可用」 | 通过 |
| AC05 服务端守卫 | `test_trpg_coc_age.py::TestAttributesNotRolled` 3 例 | 通过 |
| AC06 全量回归 | `python -m pytest -q` → **1001 passed**（5:34）；API 脚本全过；13 个 COC JS 用例全过 | 通过 |
| AC07 文档与归档 | `openspec validate coc-character-sheet --strict` valid；`CHANGELOG [2.1.1]` 与 `BOTERO_VERSION = "2.1.1"` 一致；同一 commit 归档 | 通过 |

## 行为对照

| 状态 | 之前 | 现在 |
|---|---|---|
| 无 `age_adjust` | 展开面板 | 展开面板（不变） |
| `skipped`（年龄未变） | 展开面板 + 一行小字 | **折叠成一行 + 重新应用入口** |
| `skipped`（年龄已改） | 展开面板 | 展开面板（不变） |
| `applied` | 只读明细 + 撤销 | 只读明细 + 撤销（不变） |
| 属性未填 | 可点，服务端报「教育扣减后为 0」 | 按钮禁用 + 「先掷出或填写属性」 |
