# 准备中的卡片列出群里所有人，有卡就能点开

## Why

跑团记录的「准备中」卡片只列 DM、观察者与**已经准备**的玩家。群里其他人（还没准备、或者正打算准备的人）在网页上完全看不到，也就没法提前互相看卡；而查看角色卡的接口原本只为「准备名单内」的人服务，没准备的人即使有卡也点不开。

## What Changes

- `webapp/trpg/app.py::_pending_roster`：
  - 名单改为**群里所有真人成员**（OneBot `get_group_member_list`），顺序为 DM → 观察者 → 已准备（按准备时间）→ 其余按昵称排序；机器人（`is_robot`）排除。已标记的 DM/观察者即使暂时不在成员列表里也保留。
  - 每人额外解析「当前角色卡」：已准备的用准备快照里的 `char_id`；没准备的读 `character_store.get_current()`，因此**没准备但设了当前卡的人也能点开查看**。
  - `prepared_count` 只统计名单内的人（准备完又退群的不计入），`member_count` = 名单人数。
  - 群成员接口不可用时退回原行为（pending.json 里出现的人），页面不会变空。
- 成员列表加 TTL 缓存：成功 60s、失败 30s，单次调用 `fetch_group_members(..., timeout=2)`（`core/onebot_client.py` 新增 `timeout` 参数，默认仍是 5s），避免 OneBot 不可达时每次打开页面都等超时。
- `webapp/static/trpg_records.js::partyMemberRow`：只要 `char_id` 存在整行就是链接（`?party=<群号>`，DM 仍可审私密卡）；没准备的人多一个灰色「未准备」标记；没有角色卡的人不可点，显示「等待准备」。

## Capabilities

### Modified Capabilities

- `trpg-party-roster`：准备中卡片的名单口径与可点开条件。

## Scope and Compatibility

- 聊天内的 `/跑团` 准备卡片不变（只列 DM/观察者/已准备 + 未准备 @ 列表，避免刷屏）。
- 只读：仍是 webapp 读 `pending.json` + 角色卡文件，不写任何数据。
- 群成员接口不可用、或机器人没有 `onebot.http_url` 时行为与之前一致。
- 无数据库变更；版本 1.92.0。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 全员入列 | `python test/scripts/check_trpg_party_api.py` | 打桩 4 人（含 1 机器人）后，名单包含全部真人；机器人被排除 |
| AC02 人数口径 | 同上 | `member_count` = 名单人数；`prepared_count` 只算名单内已准备者 |
| AC03 未准备也有卡 | 同上 | 未准备但有当前卡的成员 `char_id` 为其当前卡、`prepared` 为 false；DM 可 `GET /api/trpg/party/<群>/card/<他>` 拿到卡 |
| AC04 接口降级 | 同上 | `fetch_group_members` 返回 None 时名单仍含 DM 与已准备玩家 |
| AC05 前端可点 | `node test/test_trpg_records_list_dom.js` | 没准备但有卡的成员行是链接、带「未准备」标记；没卡的人不可点、显示「等待准备」 |
| AC06 全量回归 | `python -m pytest -q` | 全绿 |
| AC07 文档与归档 | `openspec validate trpg-party-roster --strict`；归档与实现同一 commit | `CHANGELOG [1.92.0]` 与 `BOTERO_VERSION` 一致 |
