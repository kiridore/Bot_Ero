# 跑团记录：用户消息先于机器人回复入档

## Why

所有者反馈：记录里 `.r` 的骰子结果排在了 `.r` 指令本身之前。

实测确认（本地复现，录制中发送 `.r 1d6`）：

```
bot  | 玩家A掷出了 1d6=[1d6=6]=6
user | .r 1d6
```

原因：`plugin_pool` 按插件注册表顺序执行，`pkgutil.walk_packages` 是字母序，`trpg_dice`、`trpg_vitals` 都排在 `trpg_session` 之前。骰子插件先跑 → 立刻 `record_bot_message()` 把回复写进 `messages.jsonl`；`trpg_session` 后跑 → 才写用户消息。所有「机器人在同一条消息里回复」的指令都受影响（`.r`、`.ra`、`.rc`、`.rh`、`.hp`、`.san`、`.mp`、`.sc`）。

## What Changes

- `core/context.py` 新增 `plugin_execution_order(registry, group_id)`：**该群正在录制时**把 `trpg_session` 排到最前，其余插件保持注册表原序；非录制状态返回原序（不改动传入列表）。
- `main.py::plugin_pool` 改用该顺序遍历。
- 测试：顺序函数 3 例（非录制保持原序 / 录制中 session 优先且稳定 / 私聊不受影响）+ 入档次序 2 例（`.r`、`.hp` 的 `messages.jsonl` 都是 user → bot）。

## Capabilities

### Modified Capabilities

- `trpg-session-recording`：同一条消息内用户消息与机器人回复的入档次序。

## Scope and Compatibility

- 仅变更**录制中**的插件执行顺序；非录制状态、其他插件之间的相对顺序完全不变。
- `trpg_char` 的 `/跑团 角色 …` 在录制中仍被 `trpg_session` 路由排除，不受影响。
- 历史记录里的错序不修复（`messages.jsonl` 是已落盘事实，改写有风险）。
- 无数据库变更、无新增依赖；版本 1.83.2。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 顺序函数 | `python -m pytest test/test_trpg_session.py -q -k ExecutionOrder` | 非录制保持原序；录制中 `TrpgSessionPlugin` 第一且其余相对顺序不变；不修改传入列表 |
| AC02 骰子入档 | `python -m pytest test/test_trpg_session.py -q -k RecordOrder` | `.r 1d6` 的 `messages.jsonl` 为 `[user, bot]`，user 段落文本为 `.r 1d6` |
| AC03 数值入档 | 同上 | `.hp -5` 同样为 `[user, bot]` |
| AC04 全量回归 | `python -m pytest -q` | 全绿 |
| AC05 文档与归档 | `openspec validate trpg-session-recording --strict`；归档与实现同一 commit | `CHANGELOG [1.83.2]` 与 `BOTERO_VERSION` 一致 |
