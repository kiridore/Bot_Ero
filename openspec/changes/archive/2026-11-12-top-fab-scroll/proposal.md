# 「回到顶部」按钮滚动后才出现

## Why

1.88.0 把三个悬浮按钮做成常驻，但页面在顶部时「回到顶部」没有意义，反而占着右下角的位置。

## What Changes

- `trpg_record.js` 新增 `syncTopFab()`：`window.scrollY < 300` 时给 `fabTop` 加 `is-hidden`、把 `tabIndex` 设为 -1（不可聚焦），否则移除；在 `mountFabs()` 初始化时执行一次，并监听 `scroll`（passive）。
- `trpg.css` 新增 `.trpg-fab-btn.is-hidden`：`opacity: 0; visibility: hidden; pointer-events: none`——保留占位，另外两个按钮不跳动。
- 「隐藏暗骰」「隐藏场外发言」两个按钮仍然常驻。

## Capabilities

### Modified Capabilities

- `trpg-record-web`：悬浮按钮的显隐。

## Scope and Compatibility

- 纯前端；不涉及数据与接口。
- `window.addEventListener` 不存在（测试环境）时跳过监听，按钮仍可手动调用 `syncTopFab()`。
- 无数据库变更、无新增依赖；版本 1.88.1。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 顶部隐藏 | `node test/test_trpg_records_dom.js` | 初始 `scrollY` 为 0 时 `fabTop` 带 `is-hidden`、`tabIndex === -1` |
| AC02 滚动后出现 | 同上 | `scrollY = 600` 后 `syncTopFab()` 移除 `is-hidden`、`tabIndex === 0` |
| AC03 样式 | 同上 | CSS 含 `.trpg-fab-btn.is-hidden` |
| AC04 另两个常驻 | 同上 | `fabSecret` / `fabOoc` 不受隐藏逻辑影响（既有断言全过） |
| AC05 全量回归 | `python -m pytest -q` | 全绿 |
| AC06 文档与归档 | `openspec validate trpg-record-web --strict`；归档与实现同一 commit | `CHANGELOG [1.88.1]` 与 `BOTERO_VERSION` 一致 |
