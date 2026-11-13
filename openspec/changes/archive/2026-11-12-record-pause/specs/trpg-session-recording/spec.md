# trpg-session-recording — 变更（暂停）

## ADDED Requirements

### Requirement: 暂停与续录
录制中 SHALL 支持 `/跑团 记录 暂停`（DM 或超级用户）：暂停后用户消息与机器人回复 MUST NOT 写入 `messages.jsonl`，会话本身保留（群仍是录制静默模式）。`meta.json` SHALL 记录 `paused` 与 `paused_at`。暂停态下 `/跑团 记录 开始` MUST 直接续录且 MUST NOT 校验准备状态；暂停与恢复各写一条机器人消息（含暂停时长）。结束录制 MUST 清除暂停标记。

#### Scenario: 暂停
- **WHEN** DM 在录制中发送 `/跑团 记录 暂停`
- **THEN** 记录里出现「录制于 HH:MM 暂停」，`meta.paused` 为 true

#### Scenario: 暂停期间发言
- **WHEN** 暂停期间有人聊天或发送 `.r 1d6`
- **THEN** 两者都不写入 `messages.jsonl`

#### Scenario: 续录
- **WHEN** 暂停后 DM 发送 `/跑团 记录 开始`
- **THEN** 立即恢复录制（不检查准备名单），写入「录制于 HH:MM 恢复（暂停 N 分钟）」，后续消息照常入档

#### Scenario: 重复暂停
- **WHEN** 已暂停时再次发送 `/跑团 记录 暂停`
- **THEN** 提示已处于暂停状态并给出继续指令

#### Scenario: 权限
- **WHEN** 非 DM 发送 `/跑团 记录 暂停`
- **THEN** 提示只有 DM 才能暂停

### Requirement: 暂停状态的重启恢复
重启时暂停中的记录 SHALL 恢复为暂停态，MUST NOT 写入中断/恢复消息，群公告 SHALL 说明当前处于暂停状态并提示用 `/跑团 记录 开始` 继续。

#### Scenario: 暂停中重启
- **WHEN** 录制处于暂停态时机器人重启
- **THEN** 会话恢复后仍为暂停态，记录里没有「中断」消息，公告提示「暂停状态」
