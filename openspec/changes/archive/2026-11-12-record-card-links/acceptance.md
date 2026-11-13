# 记录页角色卡入口 — 验收记录

实施分支：`master`；版本 1.86.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 悬停概要 | `node test/test_trpg_records_dom.js`：COC 概要含「酒保」与「SAN 60/65」；DND 含「Lv.3」与「AC 16」；无快照提示「没有角色卡快照」 | 通过 |
| AC02 地址拼装 | `charUrl({user_id:"777",char_id:9})` → `/trpg/char/777/9`；无 `char_id` → `""` | 通过 |
| AC03 头像链接 | 他人头像外层为 `<a class="trpg-card-link">`，`href=/trpg/char/12345602/12`，`title` 含「酒保」 | 通过 |
| AC04 角色卡条目 | 参团角色卡 2 条、`sheetBox.hidden=false`、每条都是 `<a>` 且带「查看角色卡 →」与 `title`；无 `char_id` 的节点不被包链接（`linkToCard` 原样返回） | 通过 |
| AC05 全量回归 | `python -m pytest -q` → **907 passed**（5:12）；DOM 套件 64 项全过 | 通过 |
| AC06 文档与归档 | `openspec validate trpg-record-web --strict` valid；`CHANGELOG [1.86.0]` 与 `BOTERO_VERSION = "1.86.0"` 一致；同一 commit 归档 | 通过 |

## 实现说明

- **列表口径放宽**：原来「参团角色卡」只列有快照的参与者（1.74 之后才写快照），现在只要有 `char_id` 就列，因此老记录里的参与者也能点进去；无快照的条目只有名字与链接。
- **概要来源**：`sheet_start` 优先、`sheet_end` 兜底，与页面里「开始 / 结束」两行的数值同源。
- **权限**：复用既有 `/trpg/char/<user>/<char>` 页面与 `/api/characters/...`；`privacy.char_public` 缺省为公开，只有显式关闭的用户会看到「对方未公开角色卡」。
- **未做**：气泡里的名字没有做链接（自己发的消息没有头像，仍可通过顶部「参团角色卡」进入）；没有做悬停浮层（用原生 `title`，零 JS、可访问，移动端不显示）。
