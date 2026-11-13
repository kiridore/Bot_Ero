# 骰子结果对齐可选（左 / 中 / 右）

## Why

记录页里骰子结果（机器人消息）原来是写死的居中窄条。有人希望它跟玩家气泡一样靠左，好顺着一条线读；也有人喜欢居中。与其替所有人定一个，不如做成可切换。

## What Changes

- `trpg_record.html` 右下角悬浮按钮组新增第 4 个按钮「骰子结果对齐」。
- `trpg_record.js`：新增 `applyDiceAlign()` / `cycleDiceAlign()`，点击在 **左 → 中 → 右** 之间循环；对齐方式通过消息容器的 `dice-left` / `dice-center` / `dice-right` 类生效，状态存 `localStorage`（`botero_trpg_dice_align`），非法值回落居中。
- `icons.js` 新增 `align-left` / `align-center` / `align-right` 三个 lucide 图标，按钮图标与 `aria-label` 跟随当前状态（如「骰子结果：居中（点击切换）」）。
- `trpg.css`：把写死的 `.trpg-msg.is-bot` 对齐规则改为由容器类驱动，三种方式各一条；气泡文字对齐同步。
- **默认居中**，与改动前完全一致。

## Capabilities

### Modified Capabilities

- `trpg-record-web`：骰子结果的对齐方式。

## Scope and Compatibility

- 纯前端；数据与接口不变；未设置过的浏览器行为与之前一致。
- `localStorage` 不可用（隐私模式）时仅本次生效。
- 同时修掉测试脚本的代理劫持问题：`test/scripts/_env.py` 把 `127.0.0.1,localhost` 写入 `no_proxy`，避免部署机设了 `HTTP(S)_PROXY` 时 `check_web_checkin_timeline.py` 报「服务器起不来」的假失败。
- 无数据库变更；版本 1.91.0。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 三种样式 | `node test/test_trpg_records_dom.js` | CSS 含 `.dice-left` / `.dice-center` / `.dice-right` 三条 `align-self` 规则，以及对应的 `text-align` |
| AC02 默认居中 | 同上 | 初始容器带 `dice-center`，按钮图标为 `align-center`、标签含「居中」 |
| AC03 循环切换 | 同上 | 点一次 → `dice-right` + 图标 `align-right` + `localStorage` 为 `right`；再点 → `dice-left`；第三次 → 回 `dice-center` 且存档为 `center` |
| AC04 非法值 | 同上 | `applyDiceAlign("diagonal")` 后回到居中并写回 `center` |
| AC05 页面元素 | 同上 | `trpg_record.html` 含 `id="fabDice"` |
| AC06 全量回归 | `python -m pytest -q` | 全绿 |
| AC07 文档与归档 | `openspec validate trpg-record-web --strict`；归档与实现同一 commit | `CHANGELOG [1.91.0]` 与 `BOTERO_VERSION` 一致 |
