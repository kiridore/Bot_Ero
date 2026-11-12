# 实施与验收任务

- [x] 1.1 `core/trpg/party.py`：`set_role(..., nickname=)` 写 `role_names`，换 DM 与 `clear_role` 清理。对应 AC01、AC02。
- [x] 1.2 `plugins/trpg_session/__init__.py`：`.dm`/`.ob` 传昵称。对应 AC01。
- [x] 1.3 `webapp/trpg/app.py` + `trpg_records.js`：名单昵称优先级与 `dm_name`。对应 AC03、AC04。
- [x] 1.4 测试：`test_trpg_session.py` 两例、`check_trpg_party_api.py` 一条、`test_trpg_party_render.js` 一条。对应 AC01–AC04。
- [x] 1.5 `CHANGELOG [1.78.1]`、`BOTERO_VERSION`、归档与实现同一 commit。对应 AC05。
