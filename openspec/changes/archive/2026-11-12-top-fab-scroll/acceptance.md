# 回到顶部按钮显隐 — 验收记录

实施分支：`master`；版本 1.88.1。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 顶部隐藏 | `node test/test_trpg_records_dom.js`：初始 `scrollY` 为 0 → `fabTop.classList.contains("is-hidden")` 为真、`tabIndex === -1` | 通过 |
| AC02 滚动后出现 | `window.scrollY = 600` 后 `syncTopFab()` → 无 `is-hidden`、`tabIndex === 0` | 通过 |
| AC03 样式 | CSS 含 `.trpg-fab-btn.is-hidden`（`opacity/visibility/pointer-events`） | 通过 |
| AC04 另两个常驻 | `fabSecret` / `fabOoc` 的既有断言（默认按下、切换、同步、localStorage）全过 | 通过 |
| AC05 全量回归 | `python -m pytest -q` → **918 passed**（5:16）；DOM 套件 85 项全过 | 通过 |
| AC06 文档与归档 | `openspec validate trpg-record-web --strict` valid；`CHANGELOG [1.88.1]` 与 `BOTERO_VERSION = "1.88.1"` 一致；同一 commit 归档 | 通过 |

## 实现说明

- 阈值常量 `TOP_FAB_THRESHOLD = 300`，改一个数字即可调整。
- 隐藏用 `opacity + visibility`（不是 `display: none`），保留占位，另外两个按钮位置稳定；同时 `tabIndex = -1` 避免键盘 Tab 停在看不见的按钮上。
- `scroll` 监听用 `{ passive: true }`；环境没有 `window.addEventListener` 时跳过，不影响手动调用。
