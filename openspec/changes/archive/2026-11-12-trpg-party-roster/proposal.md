# 网页展示跑团准备名单并支持 DM 审核角色卡

## Why

群内 `.dm` 之后，`pending.json` 里已经有 `roles`（DM/观察者）与 `prepared`（含 `char_id`、`char_name`），但网页上完全看不到——只有机器人侧的 `/跑团` 卡片会打印。DM 想开团前审核每个人的角色卡，目前只能挨个私聊要链接；而 `/trpg/records` 只读已开录的记录。

所有者的选择：名单并入 `/trpg/records` 顶部；所有登录用户可见；只列 DM/观察者/已准备玩家；**本群 DM 可绕过隐私设置查看这些人的完整角色卡**。

## What Changes

- 后端新增两个接口：
  - `GET /api/trpg/parties`：扫描 `server_data/trpg_records/<群号>/pending.json`，列出「有 DM 且尚未开录」的群，返回规则、DM、成员（user_id/nickname/role/char_id/char_name/prepared）与准备计数；`is_dm` 标记当前登录者是否为本群 DM（或超管）。
  - `GET /api/trpg/party/<群号>/card/<用户>`：返回该成员的角色卡（优先用准备快照里的 `char_id`，否则当前卡）。放行规则：本人 → 允许；本群 DM 或超管 → 允许（不受隐私限制）；其他人 → 按对方 `privacy.char_public`。成员不在名单里或该群没有准备 → 404。
- 前端 `/trpg/records` 顶部新增「准备中」区块：每个群显示群号、规则、DM、`已准备 x/y`，成员逐行列出身份徽标（DM/观察者）、角色卡名与「查看角色卡」按钮；未准备显示「等待准备」；DM 视角多一行审核提示。
- 角色卡查看页支持 `?party=<群号>`：带该参数时改走准备名单接口，从而让 DM 能打开私密卡。

## Capabilities

### New Capabilities

- `trpg-party-roster`：开团准备名单的网页展示与角色卡审核权限。

## Scope and Compatibility

- 只读现有 `pending.json`，不新增存储、不改变机器人侧行为。
- 名单只在「有 DM 且未开录」时出现；开录后从准备中列表消失，转为记录列表。
- DM/观察者的昵称在 `pending.json` 里没有存档（只有用户 ID），因此名单里以 QQ 号显示；已准备玩家显示群昵称。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 准备中列表 | `python test/scripts/check_trpg_party_api.py` | 有 DM 的群出现在列表，含成员、规则名、`已准备 1/3`；`is_dm` 对 DM 为 true、对陌生人 false |
| AC02 无 DM 不列出 | 同上 | 把唯一 DM 改成观察者后，列表为空 |
| AC03 审核权限 | 同上 | DM 可看参与者卡（含私密卡）；本人可看自己；旁观者看私密卡 403、看公开卡 200 |
| AC04 越界拒绝 | 同上 | 名单外的用户 404；没有准备的群 404 |
| AC05 页面渲染 | `node test/test_trpg_party_render.js` | 群号/规则/准备计数、DM 徽标与审核提示、已准备成员的 `/trpg/char/…?party=…` 链接、未准备「等待准备」、观察者徽标 |
| AC06 查看页门 | `node test/test_trpg_coc_view_dom.js` 与人工 | 带 `?party=` 时改走 `/api/trpg/party/<群>/card/<用户>` |
| AC07 文档与归档 | `python -m pytest -q`；`openspec validate trpg-party-roster --strict` | 全量回归绿；`CHANGELOG [1.78.0]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
