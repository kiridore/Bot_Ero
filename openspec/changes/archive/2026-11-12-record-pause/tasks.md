# 实施与验收任务

- [x] 1.1 `context.is_recording_active()`；`record_bot_message` 暂停时跳过。对应 AC03。
- [x] 1.2 `_handle_pause` / `_resume_recording` / `_write_pause_meta`，`开始` 在暂停态转续录。对应 AC01、AC02、AC04、AC05。
- [x] 1.3 `_record_user_message` 暂停时跳过；结束清除暂停标记。对应 AC03、AC06。
- [x] 1.4 `resume_session` 与恢复公告的暂停分支。对应 AC07、AC08。
- [x] 1.5 网页三态：`_record_state`、两个页面的标签与时间行、暂停徽标样式、暂停态轮询。对应 AC09。
- [x] 1.6 菜单与 `kb/QUICK_REFERENCE.md` 补指令。对应 AC11。
- [x] 1.7 测试：`TestPause` 11 例、API 脚本 3 条、两个 DOM 套件各 2-3 条。对应 AC01–AC09。
- [x] 1.8 `CHANGELOG [1.87.0]`、`BOTERO_VERSION`、归档与实现同一 commit。对应 AC10、AC11。
