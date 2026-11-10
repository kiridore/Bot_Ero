# 录制状态可从磁盘恢复：重启续录、群解散自动终止、结束即归档

## Why

所有者指令（2026-11-10）：「下一步更新重启即断线问题，移除导出功能，录制过程实时写入硬盘。」经逐项澄清后确认的目标是：

- 实时写入硬盘**在 1.62.0 已完成**（开录写 `meta.json`、逐条追加 `messages.jsonl`、图片即时下载），本次要修的是**录制状态只在内存**：bot 重启后不再记录该群消息，记录永远停在 `end: null`，既不能结束也不能导出；
- 「已结束但没导出」的记录只活在内存在 `last_completed`，重启即消失，永远产不出 `record.md`——这正是移除导出能顺带消灭的问题；
- 群被解散或机器人被踢时代录制无人收尾，该群所有非跑团插件持续静默。

## What Changes

### 1. 启动时从磁盘重建录制状态

- 新增 `plugins/trpg_session` 模块级 `recover_recordings()`，`main.py` 启动时调用（与 `who_is_spy` 的 `recover_interrupted_games()` 并列）。
- 扫描 `server_data/trpg_records/<群号>/*/meta.json`（`version == 2` 且 `end` 为 `null`），逐条判定：
  1. 群已不在群列表 → 自动结束（`end` = 最后一条消息时间）
  2. 最后一条消息时间（无消息则开录时间）距今超过 **7 天** → 自动结束
  3. 否则 → 重建录制会话，并把「中断 / 恢复」写进记录
- 启动时 `get_group_list` 不可达则跳过"群已解散"判定（不能把网络故障当解散），仍按 7 天规则处理。
- 续录后：本场开始时间取 `meta.json.start`；图片编号从 `imgs/` 现有最大编号继续；`participants` / `roles` 从 `meta.json` 恢复。

### 2. 中断留痕与恢复公告

- 续录时向 `messages.jsonl` 追加一条机器人消息：「录制于 2026-11-14 23:10 中断，2026-11-15 20:05 恢复」。
- 机器人连上 OneBot 后的第一个心跳周期（或在续录后的所在群里）发送公告：「已恢复 2026-11-13 20:00 开始的跑团录制，如需结束请由 DM 发送 /跑团 记录 结束」。公告只发一次。

### 3. 群解散 / 被踢 → 自动终止

- `plugins/trpg_session` 改为 `TimedHeartbeatPlugin` 并覆写 `should_run_on_heartbeat`，每 **5 分钟**触发一次（覆写方式与 `news` 插件一致）。
- 仅当存在录制中的群时才调用 `get_group_list`（HTTP，短超时）；返回成功且列表中没有该群 → 自动结束，`end` = 最后一条消息时间；接口失败忽略。
- 自动结束后同样生成 `record.md`（群已不在，不发群消息）。

### 4. 移除导出与合并转发，结束即归档

- 删除 `/跑团 记录 导出` 子命令与 `_handle_export`；`record.md` 在**结束录制时自动生成**（由 `messages.jsonl` 生成，格式不变）。
- 删除结束时的合并转发（`send_group_forward_msg`），只回一条：「跑团记录已结束——\n查看：<web 地址>/trpg/records/<群号>/<目录>」。
- 状态从三态塌成两态：`meta.end` 为 `null` = 录制中，否则 = 已结束；网页不再显示「已结束·未导出」「已导出」「（可能已中断）」。
- 删除 `core/context.py::last_completed` 及其读写：`开始` 不再检查"上次未导出"，`强制开始` 语义收窄为"跳过准入校验"。

### 5. 结束录制权限收紧

- `/跑团 记录 结束` 仅当前 DM 或超级用户可执行；其他人回「只有 DM 才能结束录制」。

### 6. 文档与版本

- `plugins/menu/bot_menu_text.py` 删除导出行；`kb/QUICK_REFERENCE.md`、`kb/PLUGIN_CATALOG.md`、`specs/plugin-catalog.md` 同步。
- `CHANGELOG.md` 新增 `[1.64.0]`，`BOTERO_VERSION` bump 至 1.64.0。

## Capabilities

### New Capabilities

- `trpg-recording-recovery`：启动扫描与续录判定（7 天阈值、群解散优先）、中断留痕与恢复公告、运行时群解散检测（5 分钟心跳轮询）、自动终止的 `end` 取值。

### Modified Capabilities

- `trpg-session-recording`：结束录制改为「写 `end` + 自动生成 `record.md` + 回网页链接，无导出指令、无合并转发」，结束权限收紧为 DM/超级用户。
- `trpg-record-web`：状态判定改为两态（录制中 / 已结束），移除「（可能已中断）」提示。

## Scope and Compatibility

- **不做**：运行期超时自动结束（所有者选择由 DM 自行结束）；为旧记录补生成 `record.md`；补录机器人不在线期间的消息（物理上收不到，文档注明）。
- **重启期间的消息丢失是物理限制**：机器人不在线就收不到事件，记录里会由「中断 / 恢复」消息明确标出断档。
- **被遗忘的录制**会在 7 天内于每次重启后自动恢复并让该群继续静默，这是「7 天阈值 + 不自动结束」的直接后果，靠恢复公告让群主发现。
- 旧记录（有 `record.md` 或无）都能在网页正常浏览，只是 md 有的有、有的没有。
- 社区版与私有版一致；无数据库变更；无新增第三方依赖；新增 `get_group_list` 外部调用（LLOneBot 已确认支持）。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 启动续录 | `python -m pytest test/test_trpg_session.py -q` | 预置一个 `end` 为 null 且最后消息在 7 天内的目录，调用 `recover_recordings()` 后该群进入录制状态；随后群消息照常写入原目录；`meta.start` 未改变；图片编号接着已有文件继续 |
| AC02 超时终止 | 同上专项 | 预置最后消息在 8 天前的目录，`recover_recordings()` 后该记录写入 `end`（等于最后消息时间）并生成 `record.md`，且不进入录制状态 |
| AC03 群解散终止 | 同上专项（注入假 `fetch_group_list`） | 群列表不含该群 → 自动写 `end` + `record.md`；`fetch_group_list` 返回 `None` 时**不**终止，按 7 天规则处理 |
| AC04 中断留痕 | 同上专项 | 续录后 `messages.jsonl` 末尾出现一条机器人消息，文本含「中断」「恢复」与两个时间 |
| AC05 运行时解散检测 | 同上专项 | 心跳（meta 事件）触发且 5 分钟内只执行一次；存在录制中的群时调用 `get_group_list`；群不在列表 → 该群录制结束；无录制时**不**调用群列表接口 |
| AC06 结束即归档 | 同上专项 | `/跑团 记录 结束` 写入 `end` 并生成 `record.md`，回执含网页链接；不再发送合并转发；`/跑团 记录 导出` 不再被路由 |
| AC07 结束权限 | 同上专项 | 非 DM 且非超级用户发 `/跑团 记录 结束` 被拒绝且录制继续；DM 与超级用户可结束 |
| AC08 开始与强制开始 | 同上专项 | `开始` 不再检查未导出记录；`强制开始` 只在准入校验失败时仍需可用（跳过校验），不再丢弃任何"未导出"状态 |
| AC09 网页两态 | `python test/scripts/check_trpg_records_api.py` + `node test/test_trpg_records_dom.js` | API 只返回 `recording` / `ended`；页面标签只有这两态且不含「（可能已中断）」 |
| AC10 文档与归档 | `python -m pytest -q`；`openspec validate trpg-recording-recovery --strict`；`openspec validate trpg-session-recording --strict`；`openspec validate trpg-record-web --strict` | 全量回归绿；三个能力规范校验通过；`CHANGELOG` 顶部 `[1.64.0]` 与 `BOTERO_VERSION` 一致；菜单与知识库指令表已去掉导出；归档与实现同一 commit |
| AC11 真实环境冒烟 | 部署机手工 | 开录 → 重启 bot → 群内收到恢复公告 → 继续发言可在网页看到接续 → DM 结束 → 网页与 `record.md` 都有完整记录 |
