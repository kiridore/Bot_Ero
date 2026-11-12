# 保存 DM / 观察者的昵称

## Why

准备名单上 DM 与观察者显示的是 QQ 号：`pending.json` 的 `roles` 只有 `{用户ID: "dm" | "ob"}`，昵称只存在于已准备玩家的快照里。DM 不准备、观察者也不准备，于是名单里两个人的名字都是数字。

## What Changes

- `party.set_role()` 增加 `nickname` 参数，把昵称写进 `pending.json` 新增的 `role_names`：`{用户ID: 昵称}`；未提供昵称时清掉该条（避免旧昵称残留）。换 DM 时旧 DM 的昵称一并清除。`clear_role()` 同步清除。
- `plugins/trpg_session` 的 `.dm` / `.ob` 处理把发送者昵称传进去。
- 准备名单接口：成员昵称优先取准备快照 → `role_names` → QQ 号；新增 `dm_name` 字段。
- 记录页「准备中」区块显示 `DM <昵称>`。

## Capabilities

### Modified Capabilities

- `trpg-preparation`：角色标记的昵称持久化。
- `trpg-party-roster`：名单昵称来源。

## Scope and Compatibility

- `role_names` 是可缺省的附加字段，旧 `pending.json`（没有该字段）按空处理，不升版本、不迁移。
- 录制中的角色变更仍只写记录 meta，不重建 `pending.json`（行为不变）。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 写入昵称 | `python -m pytest test/test_trpg_session.py -q -k nickname` | `.dm` 后 `roles={"111":"dm"}` 且 `role_names={"111":"老张"}`；`.ob` 追加观察者昵称 |
| AC02 换 DM 清理 | 同上 `-k replaces_old` | 换 DM 后 `roles={"222":"dm"}`，`role_names` 只剩新 DM |
| AC03 名单显示昵称 | `python test/scripts/check_trpg_party_api.py` | `dm_name=守密人`，成员行该用户 `nickname=守密人` |
| AC04 前端使用昵称 | `node test/test_trpg_party_render.js` | 传入 `dm_name` 时显示昵称，缺失时回落群号/ID |
| AC05 文档与归档 | `python -m pytest -q`；`openspec validate trpg-preparation --strict` | 全量回归绿；`CHANGELOG [1.78.1]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
