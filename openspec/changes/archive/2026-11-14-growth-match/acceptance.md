# `/跑团 成长` 可达 — 验收记录

实施分支：`master`；版本 1.98.2。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 子命令全覆盖 | `TestRoutedSubcommandsMatch::test_every_routed_subcommand_matches`：`准备 / 取消准备 / 名单 / 规则 / 成长 / 记录` 全部 True | 通过 |
| AC02 裸指令 | `test_bare_command_matches` | 通过 |
| AC03 未知子命令 | `test_unknown_subcommand_ignored`（`/跑团 乱打` → False） | 通过 |
| AC04 端到端结算 | `test_growth_command_settles_via_dispatch`：回执含「幕间成长」与「侦察」，卡上 `growth` 6、`check` 清空 | 通过 |
| AC05 全量回归 | `python -m pytest -q` → **963 passed**（5:13） | 通过 |
| AC06 文档与归档 | `openspec validate trpg-session-recording --strict` valid；`CHANGELOG [1.98.2]` 与 `BOTERO_VERSION = "1.98.2"` 一致；同一 commit 归档 | 通过 |

## 时间线（为什么一直没人发现）

| 版本 | 事件 |
|---|---|
| 1.63.0 | `match()` 引入子命令白名单（准备/名单/规则/记录） |
| 1.70.0 | 新增 `/跑团 成长`，加进 `_route()` 但**没加进白名单** |
| 1.98.1 | 同一次 `match()` 重构里仍然只有 `sub in PARTY_SUBCMDS or sub == "记录"` |
| 1.98.2 | 改成 `ROUTED_SUBCMDS` 统一常量 + 全覆盖用例 |

## 说明

- 用户先怀疑「录制中禁用了指令」：实际上录制只对 `准备/取消准备/名单/规则` 做 `_reject_if_recording()`，`成长` 从来不在被拦之列——它连 `handle()` 都没进。
- 现有测试没抓到，是因为所有用例都直接调 `handle()`；新用例显式「先 match 再 handle」。
