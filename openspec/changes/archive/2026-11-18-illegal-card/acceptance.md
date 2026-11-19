# 点数超预算的卡 — 验收记录

实施分支：`master`；版本 2.1.2。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 保存不拦 | `test_trpg_coc_legality.py`：`validate()` 不再含预算类问题 | 通过 |
| AC02 使用要拦 | 同上：职业点/兴趣点/无职业加点三种原因；DND 卡空 | 通过 |
| AC03 接口行为 | `check_trpg_coc_api.py`：超支 POST 200 + `illegal`；`activate` 400；修正后 `illegal` 空且 `activate` 200（脚本 93 项全过） | 通过 |
| AC04 QQ 切换 | `test_trpg_char.py::test_switch_refuses_over_budget_coc_card`：回执含「还不能设为当前角色」「职业点超出预算」，`set_current` 未被调用 | 通过 |
| AC05 准备 | `test_trpg_session.py::TestPrepare::test_prepare_refused_for_over_budget_card`：拒绝且 `prepared` 为空 | 通过 |
| AC06 页面 | 15 个 trpg JS 用例全过；`node --check` 通过 | 通过 |
| AC07 全量回归 | `python -m pytest -q` → **1008 passed**（5:35） | 通过 |
| AC08 文档与归档 | `openspec validate coc-character-sheet --strict` valid；`CHANGELOG [2.1.2]` 与 `BOTERO_VERSION = "2.1.2"` 一致；同一 commit 归档 | 通过 |

## 边界

| 情况 | 现在 |
|---|---|
| 超支卡保存 | 200，`illegal` 列出原因 |
| 超支卡设为当前（网页 / QQ） | 拒绝 |
| 超支卡 `/跑团 准备` | 拒绝 |
| 录制开始校验 | 列出「角色卡点数超预算」并 @ 当事人 |
| 已是当前卡、之后被改成超支 | 不自动取消当前卡；准备与开录会拦 |
| 其它结构性错误 | 仍然直接拒绝保存（不变） |
