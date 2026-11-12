# 实施与验收任务

- [x] 1.1 新建 `core/trpg/snapshots.py`：`sheet_snapshot` 与 `attach_end_snapshots`。对应 AC01、AC02。
- [x] 1.2 `core/trpg/records.py::finalize_record` 写入 `end` 时补 `sheet_end`（失败不阻断）。对应 AC02。
- [x] 1.3 `plugins/trpg_session/__init__.py`：开录与中途发言时写 `char_id` + `sheet_start`。对应 AC03。
- [x] 1.4 `webapp/static/trpg_record.html` / `trpg_record.js` / `trpg.css`：折叠区块与变化摘要。对应 AC04。
- [x] 1.5 新建 `test/test_trpg_snapshots.py`（6 例）与 `test_trpg_session.py::TestSheetSnapshots`（3 例）。对应 AC01–AC03。
- [x] 1.6 `CHANGELOG [1.74.0]`、`BOTERO_VERSION`、归档与实现同一 commit。对应 AC05。
