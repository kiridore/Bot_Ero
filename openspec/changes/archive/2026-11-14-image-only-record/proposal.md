# 纯图片消息也能入档

## Why

录制期间玩家发一张图不打字，这条消息**根本没进记录**（不是显示问题）。

根因在 `plugins/trpg_session/__init__.py::match()`：它一开始就 `msg = self._first_text()`，`if not msg: return False` —— 没有文字段的消息直接被判为「与本插件无关」。`main.py::plugin_pool` 只把 `match()` 返回 True 的插件交给 `handle()`，所以纯图片、纯 @、贴纸这类消息一律跳过，连 `_record_user_message()` 都没执行。

现有测试没抓到，是因为测试助手 `_run()` 直接调 `handle()`，绕过了 `match()`。

## What Changes

- `match()`：只有「有文字」的消息才走指令判断；没有文字时不再直接返回 False，而是继续判断「本群是否正在录制」——录制中返回 True（任何消息都要入档），非录制返回 False（行为不变）。
- 未知的 `/跑团 xxx` 仍返回 False（保持原样，避免让这类消息被路由成准备卡片）。
- 测试：新增 `TestMatchDuringRecording` 5 例，其中一例按 `plugin_pool` 的真实顺序（先 `match()` 再 `handle()`）验证图片确实落盘并写入 `messages.jsonl`。

## Capabilities

### Modified Capabilities

- `trpg-session-recording`：插件匹配与入档范围。

## Scope and Compatibility

- 只放宽「录制中无文字消息」的匹配；非录制群聊、私聊行为不变。
- 贴纸/表情等非图片附件按既有规则记为 `{"type":"other"}`，网页显示「[暂不支持的附件]」。
- 无数据库变更；版本 1.98.1。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 图片匹配 | `python -m pytest test/test_trpg_session.py -q -k MatchDuringRecording` | 录制中纯图片消息 `match("message")` 为 True |
| AC02 纯 @ 匹配 | 同上 | 录制中纯 @ 消息为 True |
| AC03 非录制不受影响 | 同上 | 非录制群聊的纯图片消息为 False |
| AC04 指令不误判 | 同上 | 录制中 `/跑团 乱打` 仍为 False |
| AC05 端到端 | 同上 | 按 match → handle 顺序调用后 `imgs/img_0001.jpg` 存在且 `messages.jsonl` 有 1 条 |
| AC06 全量回归 | `python -m pytest -q` | 全绿 |
| AC07 文档与归档 | `openspec validate trpg-session-recording --strict`；归档与实现同一 commit | `CHANGELOG [1.98.1]` 与 `BOTERO_VERSION` 一致 |
