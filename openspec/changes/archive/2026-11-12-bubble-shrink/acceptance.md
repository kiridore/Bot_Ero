# 气泡收缩 — 验收记录

实施分支：`master`；版本 1.88.2。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 容器 | `node test/test_trpg_records_dom.js`：`.trpg-msg-body` 规则含 `flex-direction: column` 与 `align-items: flex-start` | 通过 |
| AC02 对齐 | `.trpg-msg.is-self .trpg-msg-body` 含 `flex-end`；`.trpg-msg.is-bot .trpg-msg-body` 含 `center` | 通过 |
| AC03 上限 | `.trpg-bubble` 规则含 `max-width: 100%` | 通过 |
| AC04 全量回归 | `python -m pytest -q` → **918 passed**（5:18）；DOM 套件 89 项全过 | 通过 |
| AC05 文档与归档 | `openspec validate trpg-record-web --strict` valid；`CHANGELOG [1.88.2]` 与 `BOTERO_VERSION = "1.88.2"` 一致 | 通过 |

## 根因

`.trpg-msg-body` 原先没有任何 CSS 规则，是块级元素：气泡作为块级子元素撑满容器宽度（100%），而容器宽度取「名字行 / 气泡」两者内容宽度的较大值——名字行通常更宽，于是短消息气泡与名字等宽。

## 修法

`.trpg-msg-body` 改为列向 flex + `align-items: flex-start`（自己 `flex-end`、机器人 `center`），气泡从此按内容收缩；同时 `max-width: 100%` 保证长文本仍受 `.trpg-msg` 的 78%/86% 上限约束。

## 未验证

DOM 套件没有 CSS 引擎，只能断言规则存在；实际观感（气泡圆角、内边距、与名字行的视觉关系）需要在浏览器里看一眼。
