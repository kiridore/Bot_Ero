# 暗骰开关保持位置 — 验收记录

实施分支：`master`；版本 1.89.1。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 中途保持 | `node test/test_trpg_records_dom.js`：「切换暗骰时按锚点还原位置（不跳到底部）」最后一次 `scrollTo` 为 `{"top":600,"behavior":"auto"}` | 通过 |
| AC02 底部跟随 | 同文件：「在底部时切换暗骰跟随到底部」为 `{"top":1200,"behavior":"smooth"}` | 通过 |
| AC03 开关状态不变 | 既有断言（页头勾选、`aria-pressed`、4→5→4 条）全过 | 通过 |
| AC04 全量回归 | `python -m pytest -q` → **925 passed**（5:13）；DOM 套件 91 项全过 | 通过 |
| AC05 文档与归档 | `openspec validate trpg-record-web --strict` valid；`CHANGELOG [1.89.1]` 与 `BOTERO_VERSION = "1.89.1"` 一致；同一 commit 归档 | 通过 |

## 实现说明

- **锚点还原**：重载前找视口里第一条 `getBoundingClientRect().top >= 0` 的消息，记下它的下标与相对顶部偏移；重载后在 `requestAnimationFrame` 里用 `新位置 - 偏移` 还原。
- **在底部仍跟随**：`isAtBottom()` 为真时不走锚点，直接 `scrollToBottom()`——新出现的暗骰就在眼前。
- **无动画**：还原用 `behavior: "auto"`，避免「先跳再滑」的割裂感；只有跟随到底部才用 smooth。
- **未做**：切场外发言本来就不重载（纯 CSS 类），无需处理；「显示暗骰」不做增量插入（保持整页重载语义，改动面最小）。
- **验证边界**：DOM stub 的 `getBoundingClientRect` 固定返回 `top: 0`，因此断言的是「按锚点算出的目标位置」而不是真实像素还原；真实浏览器里的观感需人工确认一次。
