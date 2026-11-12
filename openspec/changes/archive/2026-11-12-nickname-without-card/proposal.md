# 取消群名片后昵称回落到 QQ 昵称

## Why

1.79.3 接住 `group_card` 通知刷新 DM/观察者昵称，但只在 `card_new` 非空时更新。**取消群名片**时 `card_new` 是空串，逻辑直接 return，网页于是永久显示已经不存在的那张旧名片。

同时确认：`.dm` / `.ob` 首次记录昵称时用的是 `sender.card or sender.nickname`，没设群名片的情况下本来就取 QQ 昵称（实测：空名片 → 「QQ昵称」，两者都空 → 「用户<QQ号>」），这部分不需要改。

## What Changes

- `core/onebot_client.py`：新增 `resolve_group_member_name(group_id, user_id)`，按群取成员显示名（名片优先，其次 QQ 昵称），3 秒超时、失败返回空串。
- `plugins/trpg_session::_handle_card_change`：`card_new` 为空时调用上面的函数取昵称；取到就写入 `role_names`，取不到才保持旧值。

## Capabilities

### Modified Capabilities

- `trpg-party-roster`：取消群名片时的昵称回落。

## Scope and Compatibility

- 只在「群名片被清空」这一个事件上多发一次 HTTP（3 秒超时），不影响其它路径。
- 接口不可用或返回空时行为与之前一致（保留旧昵称），不会报错。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 回落昵称 | `python -m pytest test/test_trpg_session.py -q -k GroupCardNotice` | `card_new` 为空且能取到昵称时，`role_names` 更新为 QQ 昵称 |
| AC02 取不到时保留 | 同上 | 取不到昵称时保留原昵称，不写盘 |
| AC03 无名片首次记录 | 同上（既有用例覆盖 `.dm`） | `.dm` 时 `sender.card` 为空仍取到昵称 |
| AC04 文档与归档 | `python -m pytest -q`；`openspec validate trpg-party-roster --strict` | 全量回归绿；`CHANGELOG [1.79.4]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
