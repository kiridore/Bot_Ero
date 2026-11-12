# 实施与验收任务

- [x] 1.1 `core/onebot_client.py`：TTL 缓存 + `use_cache` 参数 + 超时 2 秒。对应 AC03、AC04。
- [x] 1.2 `webapp/trpg/app.py::_pending_roster`：实时名片优先，回落快照与 QQ 号。对应 AC01、AC02。
- [x] 1.3 bot 侧 `group_card` 改为 `use_cache=False`。对应 AC03。
- [x] 1.4 测试：`TestMemberNameCache`（5 例）+ party API 两条断言。对应 AC01–AC04。
- [x] 1.5 `CHANGELOG [1.79.5]`、`BOTERO_VERSION`、归档与实现同一 commit。对应 AC05。
