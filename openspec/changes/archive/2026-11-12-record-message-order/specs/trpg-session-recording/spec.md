# trpg-session-recording — 变更（入档次序）

## ADDED Requirements

### Requirement: 同一条消息内的入档次序
录制期间，处理单条消息的插件执行顺序 SHALL 保证 `trpg_session` 先于其它跑团插件运行，使**用户消息的入档先于**该消息触发的机器人回复（骰子、数值变动）。非录制状态 MUST 保持注册表原顺序。

#### Scenario: 骰子指令
- **WHEN** 录制中玩家发送 `.r 1d6`
- **THEN** `messages.jsonl` 先写入该用户消息，再写入骰子结果

#### Scenario: 数值指令
- **WHEN** 录制中玩家发送 `.hp -5`
- **THEN** `messages.jsonl` 先写入该用户消息，再写入 HP 变动回报

#### Scenario: 非录制
- **WHEN** 群内没有进行中的录制
- **THEN** 插件按注册表原顺序执行，行为与之前一致
