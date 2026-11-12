# 准备名单的 DM 昵称改为实时查询

## Why

1.79.3/1.79.4 依赖 OneBot `group_card` 通知刷新昵称，但**该通知是否被 LLOneBot 推送未经验证**；不推送时就永远停留在 `.dm` 时刻的快照。所有者决定改为方案 A：由 webapp 在渲染名单时现查一次名片。

webapp 本来就在用 OneBot HTTP 拉昵称（`resolve_display_name` 等），通道是现成的。

## What Changes

- `core/onebot_client.py::resolve_group_member_name`：加 TTL 缓存——命中 60 秒、未命中 30 秒，超时 3 秒 → 2 秒；新增 `use_cache=False` 供事件驱动路径强制取最新。
- `webapp/trpg/app.py::_pending_roster`：`dm_name` 取值顺序改为「实时名片 → `.dm` 快照 → QQ 号」。
- bot 侧 `group_card` 处理保留（走 `use_cache=False`），作为快照层的补充；两条路径互不冲突。

## Capabilities

### Modified Capabilities

- `trpg-party-roster`：DM 昵称的实时性。

## Scope and Compatibility

- 每次打开 `/trpg/records` 最多为每个准备中的群发一次 `get_group_member_info`（命中缓存则零请求）；OneBot 不可达时失败结果缓存 30 秒，页面不会每次卡 2 秒。
- 实时取不到时行为不变（回落快照、再回落 QQ 号）。
- `onebot.http_url` 未配置的部署：请求立即失败并缓存，页面照常显示快照昵称。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 实时优先 | `python test/scripts/check_trpg_party_api.py` | 桩 `resolve_group_member_name → 实时名片` 时接口返回 `dm_name="实时名片"` |
| AC02 回落快照 | 同上 | 桩返回空串时 `dm_name` 回落 `role_names` 里的「守密人」 |
| AC03 缓存策略 | `python -m pytest test/test_trpg_session.py -q -k MemberNameCache` | 成功结果只请求一次；失败结果同样只请求一次；`use_cache=False` 可绕过缓存；非法 ID 返回空串 |
| AC04 名片优先昵称 | 同上 | 返回 `{"card":"", "nickname":"昵称"}` 时取「昵称」 |
| AC05 文档与归档 | `python -m pytest -q`；`openspec validate trpg-party-roster --strict` | 全量回归绿；`CHANGELOG [1.79.5]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
