# 入档次序 — 验收记录

实施分支：`master`；版本 1.83.2。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 顺序函数 | `TestPluginExecutionOrder` 3 例：非录制保持原序、录制中 `TrpgSessionPlugin` 第一且其余顺序不变、传入列表未被修改 | 通过 |
| AC02 骰子入档 | `TestRecordOrder::test_dice_reply_after_user_message`：`.r 1d6` → `[user, bot]`，user 文本 `.r 1d6` | 通过 |
| AC03 数值入档 | `TestRecordOrder::test_vitals_reply_after_user_message`：`.hp -5` → `[user, bot]` | 通过 |
| AC04 全量回归 | `python -m pytest -q` → **893 passed**（5:12） | 通过 |
| AC05 文档与归档 | `openspec validate trpg-session-recording --strict` valid；`CHANGELOG [1.83.2]` 与 `BOTERO_VERSION = "1.83.2"` 一致；同一 commit 归档 | 通过 |

## 复现与修法

修复前实测（录制中 `.r 1d6`）：

```
bot  | 玩家A掷出了 1d6=[1d6=6]=6
user | .r 1d6
```

根因：`plugin_pool` 按 `runtime_context.plugin_registry` 顺序执行，`pkgutil.walk_packages` 产生字母序，`trpg_dice` < `trpg_session`。

修法：`plugin_execution_order()` 在**录制中**把 `trpg_session` 提到最前（`list()` 拷贝后排序，不动注册表）；其它情况返回原序。

## 边界

- 只影响录制中的执行顺序；非录制状态与其它插件相对顺序不变。
- 历史记录里的错序不改写——`messages.jsonl` 是已落盘事实，重排需要重放图片/快照逻辑，收益不抵风险。
- `/跑团 …` 指令在录制中由 `trpg_session` 自己处理（`_route`），不写用户消息行；其结果本来也不入档（既有行为）。
