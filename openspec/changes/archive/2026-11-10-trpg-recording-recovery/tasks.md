# 实施与验收任务

> 提案 `proposal.md`；设计 `design.md`；规范：新增 `trpg-recording-recovery`，修改 `trpg-session-recording`、`trpg-record-web`。

## 1. 数据与外部接口

- [x] 1.1 `core/onebot_client.py`：新增 `fetch_group_list() -> set[int] | None`（HTTP `get_group_list`，超时 5 秒，失败返回 `None`）。对应 AC03、AC05。
- [x] 1.2 `core/trpg/records.py`：新增 `finalize_record(path, end_ts)`（写 `meta.end`，时间格式与开录一致）与 `last_message_time(path)`（无消息返回 `None`）；`record_md` 生成函数迁到本模块，供结束与自动终止共用。对应 AC02、AC03、AC06。
- [x] 1.3 `core/context.py`：删除 `last_completed`、`get_last_completed`、`pop_last_completed`。对应 AC08。

## 2. 录制恢复与心跳

- [x] 2.1 `plugins/trpg_session/__init__.py`：改继承 `TimedHeartbeatPlugin`，覆写 `should_run_on_heartbeat`（`meta` 事件、每 5 分钟一次、按分钟去重）；`match()` 合并心跳与消息匹配。对应 AC05。
- [x] 2.2 模块级 `recover_recordings()`：扫描 `end` 为 null 的记录目录，按「群解散 → 7 天 → 续录」判定；重建会话（start/participants/roles/dir/img_count）、追加「中断 / 恢复」机器人消息、标记 `resume_banner`；同群多目录只续最新一条，其余终止。`main.py` 启动时调用。对应 AC01、AC02、AC03、AC04。
- [x] 2.3 心跳处理：先发未完成的恢复公告；有录制时调用 `fetch_group_list`，群不在列表 → 终止该群录制并生成 md；无录制时不调用。对应 AC03、AC04、AC05。

## 3. 结束、权限与指令

- [x] 3.1 `/跑团 记录 结束`：仅 DM 或超级用户；写 `end`、生成 `record.md`、回执含网页链接；删除 `_send_forward` 与结束时的合并转发。对应 AC06、AC07。
- [x] 3.2 删除 `/跑团 记录 导出` 路由与 `_handle_export`；`开始` 去掉"上次未导出"检查；`强制开始` 只跳过准入校验。对应 AC06、AC08。
- [x] 3.3 `plugins/menu/bot_menu_text.py`：删除导出行，结束行补「仅 DM」。对应 AC10。

## 4. 网页两态

- [x] 4.1 `webapp/trpg/app.py::_record_state` 改为两态；`webapp/static/trpg_records.js`、`trpg_record.js` 删除 `STALE_SECONDS` 与「（可能已中断）」，`STATE_LABEL` 改为「录制中 / 已结束」。对应 AC09。

## 5. 测试

- [x] 5.1 `test/test_trpg_session.py`：删除导出用例；新增启动续录（含 `meta.start` 不变、图片编号接续、中断消息）、8 天超时终止、群解散终止、群列表不可达不终止、心跳 5 分钟去重与无录制不调用、结束权限、结束即生成 md 且无合并转发、导出不再路由。对应 AC01–AC08。
- [x] 5.2 `test/scripts/check_trpg_records_api.py` 与 `test/test_trpg_records_dom.js`：状态断言改两态、去掉中断提示断言。对应 AC09。

## 6. 文档与交付

- [x] 6.1 `kb/QUICK_REFERENCE.md`、`kb/PLUGIN_CATALOG.md`、`specs/plugin-catalog.md` 去掉导出、标注结束权限。对应 AC10。
- [x] 6.2 `CHANGELOG.md` 新增 `[1.64.0]`，`core/config.py::BOTERO_VERSION` bump 至 1.64.0。对应 AC10。
- [x] 6.3 全量 `pytest` 绿；三个能力的 `openspec validate --strict` 通过；逐条 AC 写 `acceptance.md`；`openspec archive 2026-11-10-trpg-recording-recovery` 与实现同一 commit。AC11 由所有者在部署机执行后补记。
