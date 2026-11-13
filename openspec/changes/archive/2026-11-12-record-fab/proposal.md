# 记录页底部悬浮按钮

## Why

记录详情页的「显示暗骰」「隐藏场外发言」在页头，长记录往下翻就够不到了；回到顶部只能手动拖。手机上尤其麻烦。

## What Changes

- 详情页底部固定一组三个圆形悬浮按钮（纵向排列，右下角）：回到顶部、隐藏暗骰、隐藏场外发言。
- 全部用图标（`core/web/static/icons.js` 新增 `arrow-up` / `eye-off` / `message-off` 三个 lucide 图标），按钮带 `title` 与 `aria-label`，切换类按钮用 `aria-pressed` 表示状态，图标按钮内不放纯文本。
- 悬浮按钮与页头勾选框**共用同一份状态**：任一处切换，另一处同步；暗骰按钮按下 = 暗骰隐藏（默认按下），场外按钮按下 = 隐藏场外（默认未按下）。
- 正文底部留出滚动余量，避免最后几条消息被按钮挡住。

## Capabilities

### Modified Capabilities

- `trpg-record-web`：详情页快捷操作。

## Scope and Compatibility

- 纯前端：`trpg_record.html` 加按钮组、`trpg_record.js` 抽出状态设置函数、`trpg.css` 加样式；`icons.js` 仅新增条目，不影响既有图标。
- 页头勾选框保留，行为不变；接口与数据不变。
- 无数据库变更、无新增依赖、无外链 CDN；版本 1.88.0。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 三按钮 | `node test/test_trpg_records_dom.js` | 页面含 `fabTop`/`fabSecret`/`fabOoc`，并加载 `/shared/icons.js` |
| AC02 图标 | 同上 | 三个按钮分别渲染 `arrow-up` / `eye-off` / `message-off` 图标，`aria-label` 为「回到顶部」「隐藏暗骰」「隐藏场外发言」 |
| AC03 回到顶部 | 同上 | 点击后调用 `window.scrollTo({top:0})` |
| AC04 暗骰同步 | 同上 | 默认 `aria-pressed=true` 且列表 4 条；点击后 `aria-pressed=false`、页头勾选变 true、列表 5 条；再点回 4 条 |
| AC05 场外同步 | 同上 | 点击后 `aria-pressed=true`、容器加 `hide-ooc`、页头勾选同步、`localStorage` 为 `1`；再点复原 |
| AC06 样式 | 同上 | CSS 含 `.trpg-fab` 与 `.trpg-fab-btn.is-active` |
| AC07 全量回归 | `python -m pytest -q` | 全绿 |
| AC08 文档与归档 | `openspec validate trpg-record-web --strict`；归档与实现同一 commit | `CHANGELOG [1.88.0]` 与 `BOTERO_VERSION` 一致 |
