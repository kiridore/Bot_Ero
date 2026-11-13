# DM 与观察者显示群昵称

## Why

DM 和观察者在跑团里是「以群身份在场」，不扮演角色，但网页上仍按玩家的口径显示角色卡名：气泡里是「艾拉（老张）」，参团角色卡条目与悬停概要也用角色名，准备中的跑团卡片还会给观察者显示「未选角色卡」。这在复盘时容易误读成「DM 也有角色」。

## What Changes

- `webapp/static/trpg_record.js`：新增 `isStaffRole()` / `personName()`；`displayName()`、参团角色卡条目、悬停概要统一按角色区分——`dm` / `ob` 只显示群昵称，其他参与者仍显示「角色名（昵称）」。
- `webapp/static/trpg_records.js`：准备中卡片的成员行，`dm` / `ob` 不再渲染角色卡名称（也不再显示「未选角色卡」），只保留昵称与角色徽标；玩家行不变。
- 测试：详情页 5 项、列表页 4 项、准备卡片 1 项。

## Capabilities

### Modified Capabilities

- `trpg-record-web`：会话记录的姓名口径。
- `trpg-party-roster`：准备中卡片的成员行。

## Scope and Compatibility

- 只改显示，`messages.jsonl`、`meta.json`、接口字段都不变（`char_name` 仍照常记录，方便以后按需切换口径）。
- DM/观察者若有角色卡，其卡片仍列在「参团角色卡」里、仍可点开，只是名字用群昵称。
- 无数据库变更、无新增依赖；版本 1.89.2。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 DM 气泡 | `node test/test_trpg_records_dom.js` | DM 消息名字行是 `老张（实时）`，不是 `艾拉（老张（实时））` |
| AC02 观察者气泡 | 同上 | `role: "ob"` 且带 `char_name` 的消息只显示昵称 |
| AC03 玩家气泡不变 | 同上 | 普通玩家仍是 `角色名（昵称）` |
| AC04 参团角色卡与概要 | 同上 | DM 的角色卡条目与悬停概要都用群昵称 |
| AC05 准备卡片 | `node test/test_trpg_records_list_dom.js` 与 `node test/test_trpg_party_render.js` | DM/观察者行不含角色卡名，也不含「未选角色卡」；玩家行仍显示角色名 |
| AC06 全量回归 | `python -m pytest -q` | 全绿 |
| AC07 文档与归档 | `openspec validate trpg-record-web --strict`；归档与实现同一 commit | `CHANGELOG [1.89.2]` 与 `BOTERO_VERSION` 一致 |
