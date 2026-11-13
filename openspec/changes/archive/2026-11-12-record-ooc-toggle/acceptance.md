# 场外发言开关 — 验收记录

实施分支：`master`；版本 1.85.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 识别规则 | `node test/test_trpg_records_dom.js`：全角 `（我去倒杯水）`、半角 `(等下，我查下规则)`、带前后空格的 `（笑）` 均判为场外；`（笑）他推门进来`、`他推门进来（笑）`、`（）`、带图片的消息都判为非场外 | 通过 |
| AC02 渲染标记 | 场外消息节点 `className` 含 `is-ooc`；普通发言不含 | 通过 |
| AC03 开关 | 勾选后 `#messageList` 有 `hide-ooc`，取消后移除；`localStorage.botero_trpg_hide_ooc` 分别为 `1` / `0` | 通过 |
| AC04 HTML/CSS | `trpg_record.html` 含 `id="oocToggle"` 与「隐藏场外发言」；`trpg.css` 含 `.trpg-thread.hide-ooc .trpg-msg.is-ooc` | 通过 |
| AC05 全量回归 | `python -m pytest -q` → **907 passed**（5:11）；DOM 套件 52 项全过 | 通过 |
| AC06 文档与归档 | `openspec validate trpg-record-web --strict` valid；`CHANGELOG [1.85.0]` 与 `BOTERO_VERSION = "1.85.0"` 一致；同一 commit 归档 | 通过 |

## 实现细节与裁定

- **默认不隐藏**：信息默认消失比多几句噪音更糟；需要的人勾一次即可，选择会记住。
- **只认纯文本消息**：含图片、@、其它附件段的消息即使文字被括号包住也不隐藏，避免误伤「（看图）」+图片这类有内容的消息。
- **括号内非空**：`（）`、`()` 这种空括号不判场外。
- **纯客户端过滤**：`messages.jsonl`、接口返回、`record.md` 都不变；切换不重新请求，轮询增量消息也自动受容器类控制。
- **降级**：`localStorage` 不可用（隐私模式）时仅本次生效，不报错。
