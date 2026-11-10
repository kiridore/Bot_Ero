# trpg-session-recording — 变更

## MODIFIED Requirements

### Requirement: 录制即落盘
开始录制时 SHALL 立即创建记录目录并写入 `meta.json`，此后每收到一条群消息 SHALL 追加一行到 `messages.jsonl`。`meta.json` SHALL 含 `version`（值为 2）、`group_id`、`group_name`、`start`、`end`、`roles`、`participants`；录制期间 `end` SHALL 为 `null`。`messages.jsonl` 每行 SHALL 为带 `time`、`sender_type`、`user_id`、`nickname`、`char_name`、`role`、`segments` 的 JSON 对象。开始录制 MUST 由当前 DM（或超级用户代行）经准入校验后触发，校验细则见 `trpg-party-setup`；校验通过时 `participants` SHALL 由准备名单预置（含 `user_id`、`nickname`、`char_name`、`role`，DM 在首位），`roles` SHALL 取当时的 DM/观察者标记；此后发言只补充名单之外的参与者。

#### Scenario: 开始录制
- **WHEN** DM 在校验通过后发送 `/跑团 记录 开始`
- **THEN** 记录目录被创建，`meta.json` 的 `version` 为 2、`start` 为当前时间、`end` 为 null、`participants` 含准备名单全员

#### Scenario: 名单外的人发言
- **WHEN** 录制进行中，一名未在准备名单内的群成员发言
- **THEN** `messages.jsonl` 追加该消息，`participants` 补充该用户

#### Scenario: 录制中发言
- **WHEN** 录制进行中群成员发送一条文本消息
- **THEN** `messages.jsonl` 追加一行，`sender_type` 为 `user`，`segments` 含该文本
