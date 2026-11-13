# 准备卡片：DM/观察者不挂角色卡，没卡不提示「等待准备」

## Why

1.92.0 把「有当前角色卡就能点开」铺到了所有人，结果 DM 与观察者也被挂上了角色卡名与入口——他们是以群身份在场的，不该有卡。另外完全没建卡的人被标成「等待准备」，读起来像在催他准备，其实他只是还没有卡。

## What Changes

- `webapp/trpg/app.py::_pending_roster`：`role` 为 `dm`/`ob` 的成员不再解析角色卡（`char_id` 为 null、`char_name` 为空）。
- `api_party_card`：目标成员是 DM 或观察者时返回 404（准备卡片不提供他们的卡入口，普通角色卡页仍可查看）。
- `webapp/static/trpg_records.js::partyMemberRow`：
  - DM / 观察者：只显示群昵称 + 角色徽标，没有角色卡名、没有链接、没有「未准备」。
  - 玩家没卡：显示「未设置角色卡」，不可点，不再出现「等待准备」。
  - 玩家有卡：整行可点；没准备时带灰色「未准备」标记。

## Capabilities

### Modified Capabilities

- `trpg-party-roster`：DM/观察者与无卡成员在准备卡片中的呈现与接口行为。

## Scope and Compatibility

- 纯展示口径 + 一个接口收紧（404），不写数据。
- DM 或观察者仍可用 `/trpg/char/<用户>/<卡号>`（普通角色卡页）查看自己的卡。
- 无数据库变更；版本 1.92.1。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 后端不带卡 | `python test/scripts/check_trpg_party_api.py` | DM 与观察者行 `char_id` 为 null、`char_name` 为空 |
| AC02 接口拒绝 | 同上 | `GET /api/trpg/party/<群>/card/<DM>` 返回 404 |
| AC03 玩家不受影响 | 同上 | 未准备但有卡的玩家仍有 `char_id`，DM 仍可看其卡 |
| AC04 前端行 | `node test/test_trpg_records_list_dom.js`、`node test/test_trpg_party_render.js` | DM/观察者行无角色卡名、无链接、无「未准备」；无卡玩家显示「未设置角色卡」且无处出现「等待准备」 |
| AC05 全量回归 | `python -m pytest -q` | 全绿 |
| AC06 文档与归档 | `openspec validate trpg-party-roster --strict`；归档与实现同一 commit | `CHANGELOG [1.92.1]` 与 `BOTERO_VERSION` 一致 |
