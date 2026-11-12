# 角色卡写入失败要给出可读原因

## Why

生产日志：`.hp 满` 报「指令处理出错」。真实原因是 `PermissionError`——网页建卡工具（webapp 进程）创建的 `server_data/trpg_chars/<用户>/` 目录，bot 进程没有写权限，`_write_json` 在目录里建临时文件被拒。这层 OSError 裸抛后被插件兜底成「指令处理出错，请检查格式」，误导排查方向（此前两轮先后怀疑过 @ 解析与消息格式）。

`.sc`、`.ra` 成长标记、`/跑团 成长`、`/跑团 角色 切换` 等所有「bot 改卡」路径都会撞同一面墙。

## What Changes

- `core/character_store.py::_write_json`：OSError 转成 `ValueError("角色卡写入失败：{原因}（目录 {路径}）")` 并记日志——单点覆盖全部写入方（update_char、set_current 的 meta.json）。
- `plugins/trpg_vitals` 两处 `except ValueError` 不再用固定文案覆盖，原样透传 store 的消息。
- dice / session 的写入已有 `except Exception` + 日志 + 友好提示，不动。

## Capabilities

### Modified Capabilities

- `trpg-vitals`：写入失败时的用户提示。

## Scope and Compatibility

- 纯错误消息改进；权限本身仍需部署侧修复（两进程运行用户不一致是环境问题，代码无法也不应绕过）。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 写入层 | `python -m pytest test/test_character_store.py -q -k OSError` | PermissionError → ValueError，消息含「角色卡写入失败」「Permission denied」与目录路径 |
| AC02 指令层 | `python -m pytest test/test_trpg_vitals.py -q -k WriteFailure` | `.hp -1` 的回复含写入失败原因，不再是「指令处理出错」 |
| AC03 全量回归 | `python -m pytest -q` | 全绿 |
| AC04 文档与归档 | `openspec validate trpg-vitals --strict`；归档与实现同一 commit | `CHANGELOG [1.82.5]` 与 `BOTERO_VERSION` 一致 |
