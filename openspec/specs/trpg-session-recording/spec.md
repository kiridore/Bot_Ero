# trpg-session-recording Specification

## Purpose
跑团录制在录制开始即把过程写入磁盘，成为网页可读的结构化数据：每次录制在 `<python_data_path>/trpg_records/<群号>/<开始时间>/` 下落 `meta.json`、`messages.jsonl` 与 `imgs/`；录制结束写入结束时间；导出时由同一份结构化数据生成 `record.md`。机器人自己在录制期间的发言（骰子结果、DM/观察者设置提示）一并入档。进程中途退出的残留录制不自动清理，也不谎报为已结束。

## Requirements

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

### Requirement: 机器人消息入档
录制期间机器人向群内发送的消息 SHALL 以 `sender_type` 为 `bot` 写入 `messages.jsonl`，包括骰子结果与 `.dm`/`.ob` 角色设置提示。暗骰（`.rh`）的掷骰结果 SHALL 同样入档，并在该行标记 `secret: true`；该结果 MUST NOT 作为普通消息发送到群内（仍按现有行为仅在私聊返回给使用者）。机器人的 QQ 与昵称 SHALL 在首次入档时加入 `participants`。

#### Scenario: 骰子结果入档
- **WHEN** 录制中群成员使用 `.rc 力量` 触发骰子结果
- **THEN** 该骰子结果以 `sender_type: "bot"` 出现在 `messages.jsonl`

#### Scenario: 暗骰入档并标记
- **WHEN** 录制中群成员使用 `.rh d20`
- **THEN** `messages.jsonl` 新增一行带 `secret: true` 的机器人消息，内容为暗骰结果；同步写入的普通机器人消息只有群内可见的「悄悄掷出骰子」提示

### Requirement: 图片即时入档
录制期间收到的图片消息 SHALL 在写入 `messages.jsonl` 前下载到该记录的 `imgs/` 目录，分段 SHALL 记录相对路径 `imgs/img_NNNN.<扩展名>`。下载失败时该分段 SHALL 标记不可用（`unavailable: true`）且不阻断录制，后续消息 SHALL 正常入档。

#### Scenario: 图片下载成功
- **WHEN** 录制中有人发送一张图片
- **THEN** `imgs/` 下出现对应文件，`messages.jsonl` 该分段含其相对路径

#### Scenario: 图片下载失败
- **WHEN** 图片地址解析失败或下载异常
- **THEN** 该分段标记不可用，录制继续，后续文本消息照常入档

### Requirement: 群名记录
录制开始时 SHALL 调用一次 `get_group_info` 取群名写入 `meta.json.group_name`。调用失败或超时时 `group_name` SHALL 写为空串且录制 SHALL 正常开始。

#### Scenario: 取群名失败
- **WHEN** `get_group_info` 返回失败或超时
- **THEN** 录制照常开始，`group_name` 为空串

### Requirement: 结束与导出
结束录制时 SHALL 在 `meta.json` 写入 `end`。导出 SHALL 从 `messages.jsonl` 生成 `record.md`（标题、开始/结束时间、参与人、逐条消息，保留 DM/观察者前缀、图片引用与 @ 提及），并 SHALL 在群内回一条成功消息，其中包含可访问的网页地址 `<web_base_url>/trpg/records/<群号>/<开始时间目录>`。

#### Scenario: 导出记录
- **WHEN** 结束录制后发送 `/跑团记录 导出`
- **THEN** 记录目录出现 `record.md`，内容与 `messages.jsonl` 对应，群内回执包含该记录的网页链接

### Requirement: 记录目录与校验集中管理
记录根路径、开始时间目录名格式与媒体文件名校验 SHALL 由一个共享模块提供（`core/trpg/records.py`），插件与 webapp MUST 共用同一实现，MUST NOT 各自硬编码相对路径；非法群号、非法目录名与非法媒体文件名 SHALL 被拒绝而不是拼进文件系统路径。

#### Scenario: 非法目录名被拒
- **WHEN** 以含 `../` 的字符串作为记录目录名调用记录模块
- **THEN** 抛出 `ValueError`，不产生任何文件访问
