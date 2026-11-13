# 切换暗骰时保持阅读位置

## Why

记录页点「显示暗骰 / 隐藏暗骰」（页头勾选框或底部悬浮按钮）会把页面甩到最底部。

根因：切换走的是 `load(true)` 全量重载，而 `load()` 里 `const stick = reset || isAtBottom()` —— 只要是 `reset` 就无条件滚到底。读者翻到中间时一按就丢位置。

## What Changes

- `load(reset, options)` 新增 `keepPosition`：为真且当前**不在底部**时，重载前记录「视口里第一条消息」及其相对视口顶部的位置，重载后（`requestAnimationFrame` 里等布局完成）用 `window.scrollTo({behavior:"auto"})` 把这同一条消息放回原处。
- 已在底部时仍按原行为跟随到底部（新增的暗骰就在眼前，不该被留在原处）。
- `setSecretHidden()` 改成 `load(true, { keepPosition: true })`；首屏加载、轮询、场外开关（纯 CSS 切换）不受影响。

## Capabilities

### Modified Capabilities

- `trpg-record-web`：暗骰开关重载时的滚动位置。

## Scope and Compatibility

- 纯前端；接口与数据不变。
- 窄屏/长记录同样生效；`requestAnimationFrame` 不存在时同步还原。
- 无数据库变更、无新增依赖；版本 1.89.1。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 中途保持 | `node test/test_trpg_records_dom.js` | `scrollY=600`（不在底部）时切换暗骰，最后一次 `scrollTo` 为 `{top:600, behavior:"auto"}`，不是滚到 1200 |
| AC02 底部跟随 | 同上 | 视为在底部时切换，最后一次 `scrollTo` 为 `{top:1200, behavior:"smooth"}` |
| AC03 开关状态不变 | 同上 | 切换后页头勾选框、按钮 `aria-pressed`、消息条数与既有断言一致 |
| AC04 全量回归 | `python -m pytest -q` | 全绿 |
| AC05 文档与归档 | `openspec validate trpg-record-web --strict`；归档与实现同一 commit | `CHANGELOG [1.89.1]` 与 `BOTERO_VERSION` 一致 |
