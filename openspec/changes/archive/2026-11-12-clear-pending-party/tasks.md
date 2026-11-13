# 实施与验收任务

- [x] 1.1 `_preparing_group_ids()` / `_drop_pending()`，心跳接入并去掉「无录制直接返回」。对应 AC01–AC03。
- [x] 1.2 `DELETE /api/trpg/party/{group_id}`（DM/超管）。对应 AC04。
- [x] 1.3 列表页「清除这条准备」按钮 + 二次确认 + 移除卡片。对应 AC05。
- [x] 1.4 测试：`TestPendingCleanup` 5 例、party API 6 条、列表 DOM 3 条。对应 AC01–AC05。
- [x] 1.5 `CHANGELOG [1.89.0]`、`BOTERO_VERSION`、归档与实现同一 commit。对应 AC06、AC07。
