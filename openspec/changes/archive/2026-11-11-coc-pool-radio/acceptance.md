# 可选池控件类型与提示样式 — 验收记录

实施分支：`master`；版本 1.73.1。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 单选池 | `test_trpg_coc.py::test_pool_single_choice_uses_radio` 通过：源码含 `const single = choice.count === 1;` 与 `input.type = single ? "radio" : "checkbox";` | 通过 |
| AC02 提示逻辑 | `test_choice_warning_toggles_class` 通过：源码含 `coc-choice-warn-on` 与「多选了」分支 | 通过 |
| AC03 样式 | `#occ-choice-warn` 默认 `display:none`，带 `coc-choice-warn-on` 时 `color: color-mix(in srgb, var(--red) 62%, var(--ink-soft))` | 代码层通过，视觉待确认 |
| AC04 文档与归档 | 全量 `pytest` → **721 passed**（4:40）；`openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.73.1]` 与 `BOTERO_VERSION = "1.73.1"` 一致 | 通过 |

## 实测与裁定

- 单选池用 `radio` 并共享 `name="occ-pool-<index>"`，浏览器原生互斥；选中即把该池的数组替换成单项。
- 多选池保持 `checkbox`，勾选集合即选择结果。
- 文本输入类池（`类别:*` / 任意项）没有控件，靠输入内容；超配额时提示「多选了 N 项」，服务端仍会 400。
- 提示色取 `--red` 62% 与 `--ink-soft` 混合，避免和真正的错误信息同权重；无提示时整行隐藏，不占位。
