# 跑团记录气泡改用 QQ 头像与实时名称

## Why

记录详情的气泡里，头像是个带名字首字的色块，名字是发送消息那一刻的昵称快照。与站内其它地方（论坛、时间线）不一致——它们都通过 OneBot 取 QQ 头像与当前显示名，换昵称后立刻更新。

## What Changes

- `webapp/trpg/app.py`：详情接口的 `participants` 增加 `display_name` 与 `avatar_url`，取法与时间线一致（`resolve_display_name` / `resolve_avatar_url`，`ThreadPoolExecutor` 并发，均带 `lru_cache`）。取不到时回落参与者快照里的昵称；不写回 `meta.json`。
- `webapp/static/trpg_record.js`：
  - 头像改为 `<img class="trpg-avatar">`（懒加载，`onerror` 回落名字首字色块）；
  - 名字统一为「角色卡名称（QQ名称）」，括号里用实时显示名，取不到回落消息里的昵称。
- `webapp/static/trpg.css`：`.trpg-avatar` 增加 `object-fit: cover`，图片与原色块共用同一尺寸/圆角。

## Capabilities

### Modified Capabilities

- `trpg-record-web`：气泡头像与名称来源。

## Scope and Compatibility

- 只改记录详情页展示；`meta.json`、`messages.jsonl` 与导出 `record.md` 都不变。
- OneBot 不可达时头像回落首字色块、名字回落消息昵称，页面不报错。
- 头像解析结果由 `lru_cache` 缓存，同一用户只查一次。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 头像图片 | `node test/test_trpg_records_dom.js` | 参与者在名单里且 `avatar_url` 非空时，气泡头像为 `IMG.trpg-avatar` 且 `src` 命中该地址 |
| AC02 头像回落 | 同上 | 没有头像地址时渲染为 `DIV.trpg-avatar`，内容为名字首字 |
| AC03 名称格式 | 同上 | 有角色卡时显示「角色名（实时名称）」；无角色卡时显示实时名称 |
| AC04 接口字段 | `python test/scripts/check_trpg_records_api.py` | 详情接口 `participants` 每项都含非空 `display_name` 与 `avatar_url` 字段 |
| AC05 文档与归档 | `python -m pytest -q`；`openspec validate trpg-record-web --strict` | 全量回归绿；`CHANGELOG [1.79.6]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
