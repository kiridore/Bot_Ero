# 跑团卡片获取群名 — 验收记录

实施分支：`master`；版本 1.79.1。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 准备名单存名 | `TestGroupNamePersistence::test_card_writes_group_name_into_pending`：`/跑团 名单` 后 `pending.group_name == "夜航团"`；`test_no_name_written_when_unavailable`：解析为空时不写入 | 通过 |
| AC02 结束补名 | `test_stop_backfills_missing_group_name`：开录时群名为空，结束录制后 `meta.group_name == "夜航团"` | 通过 |
| AC03 接口下发 | `check_trpg_party_api.py`「群名随准备名单下发」：`/api/trpg/parties` 返回 `group_name="夜航团"` | 通过 |
| AC04 卡片渲染 | `test_trpg_party_render.js`「卡片标题用群名」：出现「夜航团」且不出现「群 296470819」；「没有群名时回落群号」：无群名时显示「群 296470819」 | 通过 |
| AC05 旧文件兼容 | `read_pending` 对缺失 `group_name` 补空串；`test_trpg_session.py` 全 88 例通过 | 通过 |
| AC06 文档与归档 | 全量 `pytest` → **779 passed**（4:53）；`openspec validate trpg-session-recording --strict` valid；`CHANGELOG [1.79.1]` 与 `BOTERO_VERSION = "1.79.1"` 一致 | 通过 |

## 实测与裁定

- **根因**：`pending.json` 没有群名字段，而 webapp 不接 OneBot，因此准备中卡片只能显示群号；记录卡片则只有开录那一刻取名的机会，失败即永久为空。
- **不引入新依赖**：群名仍由 bot 侧 `cached_group_name`（模块级缓存 + 3 秒短超时）获取，写入文件后 webapp 只读。
- **补写时机**：准备卡片刷新（`/跑团`、`/跑团 名单`、`.dm`、`.ob`、准备/取消准备都会走 `_card_segments`）、结束录制、启动恢复续录。群名已在时 `set_group_name` 不写盘，`_ensure_record_group_name` 直接返回。
- **用例隔离**：`_group_name_cache` 是模块级字典，新用例在 setUp 清空并在 teardown 再清，避免跨用例污染（第一次跑就踩到了）。
- **未做**：webapp 侧无法主动取群名，因此「开录与结束都没能取名」的历史记录仍显示群号——这类记录只能在 bot 再次触发时补。
