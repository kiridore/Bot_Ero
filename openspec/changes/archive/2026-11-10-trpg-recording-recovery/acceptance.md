# 录制恢复与结束即归档 — 验收记录

实施分支：`master`；版本 1.64.0；提案 `openspec/changes/2026-11-10-trpg-recording-recovery/`。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 启动续录 | `python -m pytest test/test_trpg_session.py -q` → 65 passed。`test_resume_recent_record`：预置 `end` 为 null、最后消息 1 小时前的目录 → `recover_recordings()` 返回 1，会话目录指向原目录、`img_count` 接续为 3、`start` 保持 `2026-11-10 20:00:00`，续录后新消息写入同一目录；`test_resumed_image_number_continues`：已有 `img_0003.jpg` 时新图落 `img_0004.jpg` | 通过 |
| AC02 超时终止 | `test_stale_record_finalized`：最后消息在 8 天前 → 不续录，`end` 等于最后消息时间，`record.md` 生成 | 通过 |
| AC03 群解散终止 | `test_dissolved_group_finalized`：群列表为空集 → 写 `end` + `record.md`；`test_group_list_unavailable_still_resumes`：`fetch_group_list` 返回 `None` 时仍续录，不误杀 | 通过 |
| AC04 中断留痕与公告 | `test_resume_recent_record` 断言 `messages.jsonl` 末尾出现含「中断」「恢复」的机器人消息；`test_resume_banner_sent_once`：首个心跳发出一次 `send_group_msg` 并把 `resume_banner` 置否，第二个心跳不再发 | 通过 |
| AC05 运行时解散检测 | `TestHeartbeat`：`should_run_on_heartbeat("meta")` 在 20:05 为真、同分钟第二次为假、`message` 恒为假；无录制时不调用 `fetch_group_list`；群不在列表 → 会话消失且 `end` = 最后消息时间 | 通过 |
| AC06 结束即归档 | `TestStopArchive`：结束后 `meta.end` 有值、`record.md` 存在、回执含 `查看：<WEB_BASE_URL>/trpg/records/<群号>/<目录>`；`test_export_command_removed`：`/跑团 记录 导出` 落到列表分支（回「暂无」），不再生成文件；代码中已无 `_send_forward`/`_handle_export` | 通过 |
| AC07 结束权限 | `test_stop_requires_dm`：非 DM 发 `/跑团 记录 结束` 被回「只有 DM」，录制继续；DM 与超级用户可结束（`TestStopArchive` setUp 中用 DM 结束） | 通过 |
| AC08 开始与强制开始 | `TestGate.test_force_start_bypasses_gate` 仍通过（跳过校验）；`开始` 的"未导出"检查与其用例一并删除，`/跑团 记录 开始` 在校验通过后直接开录 | 通过 |
| AC09 网页两态 | `python test/scripts/check_trpg_records_api.py` 全过（有/无 `record.md` 的记录都返回 `ended`）；`node test/test_trpg_records_dom.js` 34 项全过（状态徽标「已结束」，无「可能已中断」） | 通过 |
| AC10 文档与归档 | `python -m pytest -q` → **564 passed**（4:19）；`openspec validate trpg-recording-recovery / trpg-session-recording / trpg-record-web --strict` 均 valid；`CHANGELOG` 顶部 `[1.64.0]` 与 `BOTERO_VERSION = "1.64.0"` 一致；菜单、`kb/QUICK_REFERENCE.md`、`kb/PLUGIN_CATALOG.md`、`specs/plugin-catalog.md` 已去掉导出并标注结束权限 | 通过 |
| AC11 真实环境冒烟 | 待所有者在部署机执行：开录 → 重启 bot → 群里收到恢复公告 → 续录可见 → DM 结束 → 网页与 `record.md` 完整 | 未执行（需真实 QQ 环境） |

## 实测与裁定

- **停止权限的身份来源**：开录成功后 `pending.json` 会被清空，DM 标记随之消失；`_is_dm_or_admin` 因此改为优先读录制会话里的 `roles`，没有会话时才读 `pending.json`。首次实现漏了这点，`/跑团 记录 结束` 被 DM 自己用也会被拒——由测试 `TestStopArchive` 抓到。
- **同群多条 `end: null`**：按 `(start, 目录名)` 倒序只续最新一条，其余立即归档（`test_only_latest_resumed_for_same_group`）。
- **启动时不发群消息**：`main.py` 在 WebSocket 建立前调用 `recover_recordings()`，此时发消息必失败；恢复公告延后到首个心跳周期，失败则下个心跳重试。
- **状态机制塌缩**：`record_state()`、网页 `/api/trpg/records` 与两个前端页面全部改为两态；`RECORD_STATES` 同步。
- **删除的代码**：`_handle_export`、`_build_record_md`（迁移为模块级 `build_record_md`）、`_send_forward`、`core/context.py::last_completed` 与其两个 helper。
- **未验证**：没有真实 QQ 环境跑过重启续录；`get_group_list` 的真实返回按 OneBot 11 标准实现（`data` 为数组，元素含 `group_id`），本机无 OneBot 无法实测。
