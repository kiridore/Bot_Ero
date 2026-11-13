# 气泡宽度随内容收缩

## Why

短消息的气泡（如「嗯」「好的」）会拉到跟发言者名字行一样宽，因为 `.trpg-msg-body` 没有任何样式，是普通块级元素：气泡作为块级子元素撑满容器，而容器宽度由名字行（名字 + DM 徽标 + 时间）决定。

## What Changes

- `.trpg-msg-body` 改为列向 flex、`align-items: flex-start`、`min-width: 0`、`max-width: 100%`：气泡按自身内容收缩，不再跟随名字行宽度。
- `.trpg-msg.is-self .trpg-msg-body` 用 `flex-end`（自己的气泡靠右），`.trpg-msg.is-bot .trpg-msg-body` 用 `center`（机器人窄条居中）。
- `.trpg-bubble` 加 `max-width: 100%`：长消息仍受 `.trpg-msg` 的 78% / 86% 上限约束，不会溢出。

## Capabilities

### Modified Capabilities

- `trpg-record-web`：气泡布局。

## Scope and Compatibility

- 纯样式，不改 DOM 结构与数据；图片气泡的 `max-width: 240px` 仍然生效。
- 无数据库变更、无新增依赖；版本 1.88.2。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 容器 | `node test/test_trpg_records_dom.js` | `.trpg-msg-body` 规则含 `flex-direction: column` 与 `align-items: flex-start` |
| AC02 对齐 | 同上 | 自己用 `flex-end`、机器人用 `center` 变体规则存在 |
| AC03 上限 | 同上 | `.trpg-bubble` 含 `max-width: 100%` |
| AC04 全量回归 | `python -m pytest -q` | 全绿 |
| AC05 文档与归档 | `openspec validate trpg-record-web --strict`；归档与实现同一 commit | `CHANGELOG [1.88.2]` 与 `BOTERO_VERSION` 一致 |
