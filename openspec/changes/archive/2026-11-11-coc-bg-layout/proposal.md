# COC 建卡页背景区改为两列大输入框

## Why

背景区的九项输入沿用属性区的自适应网格（`minmax(160px, 1fr)`），宽屏会挤成 4–5 列，每格只有 160px；文本框 `rows=2`，写「思想与信念」这种长句时只露出一行半，实际不可用。

## What Changes

- 背景区独立为 `.coc-bg` 两列网格（宽屏一行两个）。
- 背景文本框最小高度 5.5rem、行高 1.5、可垂直拖拽拉伸。
- 窄屏（≤640px）回落为一列。
- 调查员笔记由 `rows=3` 改为 `rows=4`。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：背景区布局与输入框尺寸。

## Scope and Compatibility

- 纯样式与标记调整，不动取值/保存逻辑（仍按 `data-bg` 收集）。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 两列布局 | `node --check webapp/static/trpg_coc.js`；人工看 `/trpg/coc` | 宽屏背景区每行两个输入框，窄屏一列 |
| AC02 输入框尺寸 | 人工 | 背景文本框最小高度 5.5rem，可拖拽拉高 |
| AC03 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿；`CHANGELOG [1.71.3]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
