# 清理准备中残留 — 验收记录

实施分支：`master`；版本 1.89.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 解散自动清理 | `TestPendingCleanup`：群列表 `{999}` → `pending.json` 删除；`{GROUP_ID}` → 保留；`None`（接口失败）→ 保留 | 通过 |
| AC02 空转不查群 | `test_no_pending_no_recording_skips_query`：`fetch_group_list` 未被调用 | 通过 |
| AC03 录制+准备并存 | `test_recording_and_pending_both_handled`：一次心跳里录制按解散归档、`pending.json` 同时清除 | 通过 |
| AC04 手动删除 | `check_trpg_party_api.py`：DM 200、旁观者 403、重复 404、超管 200；删后列表为空、`pending.json` 不存在 | 通过 |
| AC05 页面按钮 | `test_trpg_records_list_dom.js`：`can_audit` 卡片含 `data-clear-party` 与「清除这条准备」，非 DM 不含 | 通过 |
| AC06 全量回归 | `python -m pytest -q` → **925 passed**（5:14） | 通过 |
| AC07 文档与归档 | `openspec validate trpg-session-recording --strict` valid；`CHANGELOG [1.89.0]` 与 `BOTERO_VERSION = "1.89.0"` 一致 | 通过 |

## 根因

`pending.json` 只在三种情况下被处理：开录成功（`party.clear_all`）、手动「取消准备」（只删自己的条目）、`/跑团 规则` 等写操作。**群解散**从来没有任何清理路径，网页 `/api/trpg/parties` 又只读，于是形成永久残留。

## 修法

1. **心跳兜底**：与录制解散判定同一处，扩展到 `pending.json` 存在的群；只在群列表调用成功时动作。
2. **手动入口**：`DELETE /api/trpg/party/{group_id}`，权限与本群 DM 审核一致（DM 或超管），页面上只在 `can_audit` 时渲染按钮。
3. 心跳原先「没有录制就 return」，现在只要有待清理的准备记录也会拉群列表（每 5 分钟一次，代价可接受）。

## 未做

- 群还在、只是不准备开团的情况仍需手动点「清除这条准备」（不做「多久没人准备就自动删」的启发式）。
- 删除不留审计记录。
