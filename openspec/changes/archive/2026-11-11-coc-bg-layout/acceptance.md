# COC 背景区两列大输入框 — 验收记录

实施分支：`master`；版本 1.71.3。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 两列布局 | `.coc-bg{grid-template-columns: repeat(2, minmax(0,1fr))}` + `@media (max-width:640px){grid-template-columns:1fr}`；`node --check trpg_coc.js` 通过 | 代码层通过，视觉待确认 |
| AC02 输入框尺寸 | `.coc-bg textarea{min-height:5.5rem; line-height:1.5; resize:vertical}`；调查员笔记 `rows=4` | 代码层通过，视觉待确认 |
| AC03 文档与归档 | 全量 `pytest` → **688 passed**（4:47）；`openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.71.3]` 与 `BOTERO_VERSION = "1.71.3"` 一致 | 通过 |

## 实测与裁定

- 背景区本来就带着 `coc-bg` 这个类名，但从没写对应样式，所以一直按属性区的 `minmax(160px,1fr)` 排——宽度一宽就挤成 4–5 列。
- 只加 CSS 与 `rows` 属性，取值仍走 `data-bg`，保存逻辑未变。
- 未给「克苏鲁神话」数字框改尺寸（`coc-num` 固定 5.5rem，两列下仍有富余）。
