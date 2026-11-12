# 实施与验收任务

- [x] 1.1 `plugins/trpg_session/__init__.py`：新增 `_human_members`，卡片与开录校验共用。对应 AC01、AC03。
- [x] 1.2 `test/test_trpg_session.py`：新增 `test_card_excludes_bot_from_pending`（含机器人自己与另一个机器人）。对应 AC01。
- [x] 1.3 反向验证：把过滤改回原样确认用例失败。对应 AC02。
- [x] 1.4 `CHANGELOG [1.77.3]`、`BOTERO_VERSION`、归档与实现同一 commit。对应 AC04。
