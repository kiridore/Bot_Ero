# `/跑团 成长` 收不到指令

## Why

`/跑团 成长` 从来没有生效过（与录制无关）。

`plugins/trpg_session/__init__.py::match()` 在 1.63.0 引入了子命令白名单：

```python
return sub == "" or sub in PARTY_SUBCMDS or sub == "记录"
```

而「成长」是 1.70.0 才加进 `_route()` 的，白名单没同步。`main.py::plugin_pool` 只把 `match()` 为 True 的插件交给 `handle()`，于是这条指令在框架层就被挡掉，`_handle_growth()` 一次都没执行过——录制中、录制外都一样。

## What Changes

- 新增 `ROUTED_SUBCMDS = PARTY_SUBCMDS | {"记录", "成长"}`，`match()` 改用它判断，注释写明「新增子命令要同步这里」。
- 测试：新增 `TestRoutedSubcommandsMatch` 4 例——遍历 `ROUTED_SUBCMDS` 逐个断言能匹配、裸 `/跑团` 能匹配、未知子命令仍被忽略，以及一条按「先 match 再 handle」的真实顺序跑的端到端用例（COC 卡带成长标记 → 结算 → 技能 +6 且标记清空）。

## Capabilities

### Modified Capabilities

- `trpg-session-recording`：指令匹配范围（含幕间成长）。

## Scope and Compatibility

- 只让本来就在 `_route()` 里的 `成长` 子命令真正可达；其它子命令行为不变。
- 无数据库变更；版本 1.98.2。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 子命令全覆盖 | `python -m pytest test/test_trpg_session.py -q -k RoutedSubcommands` | `准备/取消准备/名单/规则/成长/记录` 逐个 `match` 为 True |
| AC02 裸指令 | 同上 | `/跑团` 为 True |
| AC03 未知子命令 | 同上 | `/跑团 乱打` 为 False |
| AC04 端到端结算 | 同上 | `match → handle` 后回执含「幕间成长」与技能名，卡上 growth 增加、check 清空 |
| AC05 全量回归 | `python -m pytest -q` | 全绿 |
| AC06 文档与归档 | `openspec validate trpg-session-recording --strict`；归档与实现同一 commit | `CHANGELOG [1.98.2]` 与 `BOTERO_VERSION` 一致 |
