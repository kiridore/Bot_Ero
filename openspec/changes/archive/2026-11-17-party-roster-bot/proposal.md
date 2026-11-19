# 准备中卡片把机器人列进了成员名单

## Why

1.92.0 起，「准备中」卡片改为列出群里的全部真人成员，过滤条件是 `OneBot 成员列表的 is_robot`。但机器人**自己的账号**在 `get_group_member_list` 的返回里往往不带 `is_robot`（该字段标的是「其他机器人账号」），于是小埃自己作为一条普通成员出现在名单里。

对照证据：`plugins/trpg_session/__init__.py::fetch_group_members` 的使用处（群内准备卡片）本来就同时排掉了 `is_robot` 与 `BOT_QQ`；`webapp/trpg/app.py::_pending_roster` 只排了 `is_robot`，两处口径不一致。

## What Changes

- `webapp/trpg/app.py::_pending_roster`：`humans` 过滤加上 `str(user_id) != str(core_config.BOT_QQ)`，与群内卡片一致。
- `test/scripts/check_trpg_party_api.py`：把原来的假成员列表改成真实世界的两种机器人——自己的账号 `is_robot: False`、别人的机器人 `is_robot: True`；断言两者都不在名单里。

## Capabilities

### Modified Capabilities

- `trpg-party-roster`：准备中卡片的成员范围（排除机器人自身）。

## Scope and Compatibility

- 只影响 webapp 的 `/api/trpg/parties` 名单；群内 `/跑团` 卡片、审核接口、角色卡查看都不变。
- 无数据库变更；版本 1.99.1。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 机器人自己不进名单 | `python test/scripts/check_trpg_party_api.py` | 「机器人不进名单」通过，名单里没有 `BOT_QQ` |
| AC02 别的机器人也不进 | 同上 | `is_robot: True` 的账号同样被排除 |
| AC03 该用例能抓住回归 | 把过滤条件临时改回只判 `is_robot` 后重跑 | 该检查变 FAIL，输出里出现 `3915014383` |
| AC04 真人名单不受影响 | 同上 | DM / 玩家 / 观察者 / 未准备路人仍在名单里 |
| AC05 全量回归 | `python -m pytest -q` | 全绿 |
| AC06 文档与归档 | `openspec validate trpg-party-roster --strict`；归档与实现同一 commit | `CHANGELOG [1.99.1]` 与 `BOTERO_VERSION` 一致 |
