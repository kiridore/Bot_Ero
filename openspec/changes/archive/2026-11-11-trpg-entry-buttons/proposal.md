# 车卡入口按钮排列与配色统一

## Why

`/trpg` 列表页右上角的两个「新建」入口分散在标题行两端、样式不一致（DND 为实心 primary、COC 为描边），既不好看也让人误以为只有一个主入口。

## What Changes

- 两个入口收进同一个操作容器（`.trpg-head-actions`），右对齐、间距 0.5rem、窄屏自动换行。
- 两个按钮统一为同一种样式（`.btn-sm`，不再有一个 primary），地位平等。
- 顺序改为「新建 DND 5E 卡」在前、「新建 COC 7th 卡」在后（默认规则优先）。
- 空状态文案改为同时指出两个入口。

## Capabilities

### Modified Capabilities

- `dnd-character-builder`：新增「建卡入口」要求（列表页两个入口的布局与样式）。

## Scope and Compatibility

- 只改列表页标题行的 DOM 结构与一条 CSS 规则，不动任何接口与数据。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 结构 | `node --check webapp/static/trpg.js`；`python -m pytest test/test_dom_render_suites.py -q` | 两个按钮位于同一 `.trpg-head-actions` 容器内，DOM 用例全绿 |
| AC02 样式 | 人工检查 `/trpg` | 两个按钮同色同尺寸、右对齐、间距一致，窄屏换行不重叠 |
| AC03 文案与归档 | `python -m pytest -q`；`openspec validate dnd-character-builder --strict` | 空状态文案提到两种卡；`CHANGELOG [1.71.1]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
