# 清理准备中残留的跑团记录

## Why

设了 DM、玩家也准备了，但团没开起来群就解散了 —— `pending.json` 留在 `server_data/trpg_records/<群号>/` 里，网页的「准备中」卡片就永远挂着，而且没有任何删除入口（`/api/trpg/parties` 只读）。

## What Changes

- **自动清理**：心跳（每 5 分钟）除了检查录制中的群，也检查有 `pending.json` 的群；`get_group_list` 调用成功且不含该群时删掉 `pending.json`。接口失败一律不动。
- **手动清理**：新增 `DELETE /api/trpg/party/{group_id}`（本群 DM 或超级用户），删除准备中的记录；记录列表页的「准备中」卡片在该身份下多一个「清除这条准备」按钮（二次确认）。
- 心跳原先「没有录制就直接返回」，现在只要有准备中的记录也会拉一次群列表。

## Capabilities

### Modified Capabilities

- `trpg-session-recording`：心跳的群解散判定范围扩展到准备中的群。
- `trpg-party-roster`：准备中记录的删除入口。

## Scope and Compatibility

- 只删 `pending.json`，不动该群目录下已结束的记录目录。
- 群还在但放弃开团时，仍需要 DM/超管手动点「清除这条准备」。
- 无数据库变更、无新增依赖；版本 1.89.0。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 解散自动清理 | `python -m pytest test/test_trpg_session.py -q -k PendingCleanup` | 群列表成功且不含该群 → `pending.json` 被删；群仍在则保留；接口失败保留 |
| AC02 空转不查群 | 同上 | 既无录制也无待清理记录时 `get_group_list` 不被调用 |
| AC03 录制+准备并存 | 同上 | 同一次心跳里录制归档与准备清理都执行 |
| AC04 手动删除 | `python test/scripts/check_trpg_party_api.py` | DM 删除 200、旁观者 403、重复删除 404、超管 200；删后列表为空且 `pending.json` 不存在 |
| AC05 页面按钮 | `node test/test_trpg_records_list_dom.js` | `can_audit` 时卡片含 `data-clear-party` 与「清除这条准备」，否则不含 |
| AC06 全量回归 | `python -m pytest -q` | 全绿 |
| AC07 文档与归档 | `openspec validate trpg-session-recording --strict`；归档与实现同一 commit | `CHANGELOG [1.89.0]` 与 `BOTERO_VERSION` 一致 |
