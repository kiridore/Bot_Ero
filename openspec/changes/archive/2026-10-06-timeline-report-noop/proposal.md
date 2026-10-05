# 时间线上报可关（社区版 T0.3）

## Why

社区版（`bot.edition: community`）为纯 bot 部署，不运行 webapp/Event Server，`config.yaml` 不含 `timeline` 节。时间线上报客户端必须在这种形态下完全静默关闭，否则每次插件触发事件都会对空地址发起请求、抛异常刷日志。对应社区版开发计划任务 T0.3（`docs/community/development-plan.md`，M0 清障批次）。

## What Changes

- `timeline.url` 留空（缺失或空串）时，时间线上报完全关闭：不发任何 HTTP 请求、不抛异常、不阻塞调用方
- `core/config.py`：`TIMELINE_URL`/`TIMELINE_TOKEN` 缺省为空串（`timeline` 节本身按 edition 分侧必填，T0.1 已解除社区形态必填）
- **私有形态零变化（硬底线）**：配置了 `timeline.url` 的私有部署行为与现状完全一致，含重试与 best-effort 契约

> **状态说明**：实现已随 1.45.2（`70f1e2d`，2026-09-11）落地——`core/timeline_client.py` 的 `_post`/`_request` 空值守卫 + `core/config.py` 空串缺省，CHANGELOG 已记录。本提案剩余工作 = 补回归测试断言 + 勾选开发计划进度，属收尾固化，非从零开发。

## Capabilities

- **New Capabilities**：`timeline-reporting`——bot 侧时间线上报客户端的行为契约（开关语义、best-effort 契约、私有形态零变化）。openspec/specs 当前为空，本 capability 为首个。
- **Modified Capabilities**：无。

## Impact

- 代码：`core/timeline_client.py`（已改）、`core/config.py`（已改）；本提案新增测试 `test/test_timeline_noop.py`
- 调用方（checkin / checkin_recall / roll_back / activity / forum_notify / weekly_report / webapp 侧）：零改动——best-effort 契约不变，空配置下只是从"报错"变"静默"
- 文档：`docs/community/development-plan.md` 勾选 T0.3；CHANGELOG 已在 1.45.2 记录（本提案收尾记 `[未发布]` 不 bump）
