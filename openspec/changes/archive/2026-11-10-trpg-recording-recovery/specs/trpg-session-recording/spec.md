# trpg-session-recording — 变更（结束即归档）

## RENAMED Requirements

- FROM: `### Requirement: 结束与导出`
- TO: `### Requirement: 结束与归档`

## MODIFIED Requirements

### Requirement: 结束与归档
结束录制时 SHALL 在 `meta.json` 写入 `end`，并 SHALL 由 `messages.jsonl` 自动生成 `record.md`（标题、开始/结束时间、参与人、逐条消息，保留 DM/观察者前缀、图片引用与 @ 提及），群内回执 SHALL 包含可访问的网页地址 `<web_base_url>/trpg/records/<群号>/<开始时间目录>`。结束录制 SHALL 仅允许当前 DM 或超级用户执行，其他人 MUST 被拒绝且录制继续。本能力 MUST NOT 提供导出指令，MUST NOT 在结束时发送合并转发。`record.md` 生成失败 SHALL NOT 阻断结束流程，但 SHALL 在回执中说明。

#### Scenario: 导出记录
- **WHEN** 一条记录结束后查看记录目录
- **THEN** `record.md` 已由结束流程自动生成，无需任何导出指令

#### Scenario: DM 结束录制
- **WHEN** DM 发送 `/跑团 记录 结束`
- **THEN** `meta.end` 写入当前时间、`record.md` 生成、回执包含网页链接，且不发送合并转发

#### Scenario: 非 DM 结束录制
- **WHEN** 非 DM 且非超级用户发送 `/跑团 记录 结束`
- **THEN** 机器人拒绝并提示只有 DM 才能结束，录制状态保持不变

#### Scenario: 导出指令已移除
- **WHEN** 发送 `/跑团 记录 导出`
- **THEN** 机器人列出记录列表（按未知子命令处理），不会生成任何文件
