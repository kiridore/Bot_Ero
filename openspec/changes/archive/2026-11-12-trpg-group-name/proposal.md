# 跑团卡片获取群名

## Why

两处卡片拿不到群名：

1. **准备中卡片**（1.78.0 加到 `/trpg/records` 顶部）只显示 `群 <QQ群号>`。根因是 `pending.json` 从来没存群名，而 webapp 是独立进程、**无法调用 OneBot**，只能读文件——群名在 bot 侧是可得的，却没落盘。
2. **记录卡片**依赖开录那一刻的 `meta.group_name`。若当时 OneBot HTTP 不可达（`onebot.http_url` 未配置或超时），`meta.group_name` 永远是空串，记录列表就退回显示 `团 <QQ群号>`，之后也不会再有第二次机会补上。

## What Changes

- `core/trpg/party.py`：`pending.json` 增加 `group_name` 字段（旧文件缺失按空串处理，不强制重写）；新增 `set_group_name()`，名字没变不写盘。
- `plugins/trpg_session`：刷新准备情况卡片时把群名写进 `pending.json`（`cached_group_name` 有缓存，不会每次打接口）；新增 `_ensure_record_group_name()`，在结束录制、启动恢复续录时若 `meta.group_name` 为空则补一次。
- `webapp/trpg/app.py`：`/api/trpg/parties` 下发 `group_name`。
- `webapp/static/trpg_records.js`：准备中卡片标题与表头优先用群名，缺失时回落 `群 <群号>`。

## Capabilities

### Modified Capabilities

- `trpg-session-recording`：群名的获取、落盘与展示。

## Scope and Compatibility

- `pending.json` 新增字段可选，旧文件读取时补空串；不 bump `pending` 版本、不迁移。
- 群名仍然只是展示信息：取不到时一切流程照常（回执、录制、校验都不受影响）。
- 记录若在开录与结束都取不到群名，仍会回落显示群号（webapp 无法自行取群名）。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 准备名单存名 | `python -m pytest test/test_trpg_session.py -q -k GroupNamePersistence` | `/跑团 名单` 后 `pending.json.group_name` 为解析到的群名；接口不可用时不写入 |
| AC02 结束补名 | 同上 | 开录时群名不可用（meta 为空），结束录制后 `meta.group_name` 补上 |
| AC03 接口下发 | `python test/scripts/check_trpg_party_api.py` | `/api/trpg/parties` 返回 `group_name="夜航团"` |
| AC04 卡片渲染 | `node test/test_trpg_party_render.js` | 有群名时标题显示群名且不出现「群 <群号>」；无群名时回落「群 <群号>」 |
| AC05 旧文件兼容 | `python -m pytest test/test_trpg_session.py -q` | 没有 `group_name` 的 `pending.json` 读取不报错、按空串处理 |
| AC06 文档与归档 | `python -m pytest -q`；`openspec validate trpg-session-recording --strict` | 全量回归绿；`CHANGELOG [1.79.1]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
