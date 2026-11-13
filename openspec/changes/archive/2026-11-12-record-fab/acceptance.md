# 悬浮按钮 — 验收记录

实施分支：`master`；版本 1.88.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 三按钮 | `node test/test_trpg_records_dom.js`：HTML 含 `fabTop`/`fabSecret`/`fabOoc` 与 `/shared/icons.js` | 通过 |
| AC02 图标 | 三个按钮 `innerHTML` 分别含 `data-icon="arrow-up"` / `"eye-off"` / `"message-off"`；`aria-label` 为「回到顶部」「隐藏暗骰」「隐藏场外发言」 | 通过 |
| AC03 回到顶部 | 点击后最后一次 `window.scrollTo` 的 `top` 为 0 | 通过 |
| AC04 暗骰同步 | 初始 `aria-pressed=true` + 列表 4 条；点击后 `aria-pressed=false`、`revealToggle.checked=true`、列表 5 条；再点回 4 条 | 通过 |
| AC05 场外同步 | 点击后 `aria-pressed=true`、容器有 `hide-ooc`、`oocToggle.checked=true`、`localStorage` 为 `1`；再点复原 | 通过 |
| AC06 样式 | CSS 含 `.trpg-fab` 与 `.trpg-fab-btn.is-active` | 通过 |
| AC07 全量回归 | `python -m pytest -q` → **918 passed**（5:07）；DOM 套件 82 项全过 | 通过 |
| AC08 文档与归档 | `openspec validate trpg-record-web --strict` valid；`CHANGELOG [1.88.0]` 与 `BOTERO_VERSION = "1.88.0"` 一致；同一 commit 归档 | 通过 |

## 实现说明

- **状态唯一**：新增 `secretHidden` / `oocHidden` 两个变量，`setSecretHidden()` / `setOocHidden()` 同时更新页头勾选框、按钮 `aria-pressed` 与视觉效果，避免两套控件各记一份状态。
- **默认值**：暗骰默认隐藏（按钮按下），场外默认显示（按钮未按下），与页头一致。
- **图标来源**：`core/web/static/icons.js`（自托管 lucide，无外链），新增三条 path；按钮内不放任何文字，标签只出现在 `title` / `aria-label`。
- **布局**：右下角纵向排列，`position: fixed; z-index: 40`；窄屏缩小到 2.35rem；`.trpg-thread` 加 `padding-bottom: 5rem` 防止挡内容。
- **降级**：图标库缺失时按钮仍可点击（仅无图形），`window.scrollTo` 不存在时不报错。
