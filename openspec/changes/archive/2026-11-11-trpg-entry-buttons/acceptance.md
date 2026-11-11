# 车卡入口按钮 — 验收记录

实施分支：`master`；版本 1.71.1。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 结构 | `node --check webapp/static/trpg.js` 通过；`test_dom_render_suites.py` 19 passed；`renderList` 中两按钮同属 `.trpg-head-actions`，DND 先入容器 | 通过 |
| AC02 样式 | `.trpg-head-actions{display:flex; align-items:center; gap:.5rem; flex-wrap:wrap; flex-shrink:0}`，两个按钮均为 `.btn-sm`（无 primary）；`.section-head` 的 `space-between` 使容器整体右对齐 | 代码层通过，视觉效果待人工确认 |
| AC03 文案与归档 | `python -m pytest -q` → **686 passed**（4:47）；空状态文案改为「点右上角『新建 DND 5E 卡』或『新建 COC 7th 卡』」；`CHANGELOG [1.71.1]` 与 `BOTERO_VERSION = "1.71.1"` 一致；`openspec validate` valid | 通过 |

## 实测与裁定

- 根因是 `.section-head` 使用 `justify-content: space-between`，三个子元素（标题 + 两个按钮）被均匀推开，加上一个带 `primary` 一个不带，看起来像「一个主按钮 + 一个附属按钮」。
- 改法是把两个按钮包进独立 flex 容器，标题与容器形成左右两组；两按钮同色。
- 未改按钮文案以外的任何交互，未触动接口。
