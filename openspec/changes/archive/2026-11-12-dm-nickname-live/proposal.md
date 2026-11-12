# 群名片变更实时刷新 DM/观察者昵称

## Why

准备名单里的 DM 昵称是 `.dm` 那一刻的快照（`pending.json.role_names`）。DM 之后改群名片、改名，网页上仍是旧名字，除非他再发一次 `.dm`。webapp 是独立进程、不调 OneBot，无法自己取最新名片。

## What Changes

- `plugins/trpg_session`：`match()` 接住 `notice_type == "group_card"` 事件，`_handle_card_change()` 把 `card_new` 写回 `pending.json` 的 `role_names`。
- `core/trpg/party.py`：新增 `update_role_nickname()`，只在目标用户**已有 DM/观察者标记**时写盘（避免为任意成员的名片变更凭空创建 `pending.json`），名字没变化不写。
- 记录中的参与者昵称不受影响（消息自带昵称）。

## Capabilities

### Modified Capabilities

- `trpg-party-roster`：DM/观察者昵称的实时性。

## Scope and Compatibility

- 依赖 OneBot `notice_type == "group_card"`（OneBot 11 标准，LLOneBot 是否推送需部署后实测；不推送时行为与现在一致，不会报错）。
- 只更新 `role_names`，不动 `roles`、准备快照与记录文件。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 DM 名片 | `python -m pytest test/test_trpg_session.py -q -k GroupCardNotice` | `.dm` 后收到 `group_card`，`role_names` 更新为新名片 |
| AC02 观察者名片 | 同上 | `.ob` 后同样更新 |
| AC03 无角色用户 | 同上 | 没有 DM/观察者标记的用户改名片不创建 `pending.json` |
| AC04 空名片 | 同上 | `card_new` 为空时保留原昵称 |
| AC05 其它通知 | 同上 | `group_recall` 等 notice 不匹配本插件 |
| AC06 文档与归档 | `python -m pytest -q`；`openspec validate trpg-party-roster --strict` | 全量回归绿；`CHANGELOG [1.79.3]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
