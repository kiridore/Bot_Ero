# 实施与验收任务

- [x] 1.1 `core/trpg/party.py`：`group_name` 字段 + `set_group_name()` + 旧文件补默认。对应 AC01、AC05。
- [x] 1.2 `plugins/trpg_session`：刷新准备卡片时写群名；`_ensure_record_group_name()` 用于结束与恢复续录。对应 AC01、AC02。
- [x] 1.3 `webapp/trpg/app.py` 下发 `group_name`；`trpg_records.js` 优先用群名。对应 AC03、AC04。
- [x] 1.4 测试：`TestGroupNamePersistence`（3 例）、party API 断言、render 断言（含回落）。对应 AC01–AC05。
- [x] 1.5 `CHANGELOG [1.79.1]`、`BOTERO_VERSION`、归档与实现同一 commit。对应 AC06。
