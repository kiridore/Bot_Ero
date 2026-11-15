# trpg-session-recording — 变更（无文字消息入档）

## ADDED Requirements

### Requirement: 录制中无文字的消息同样入档
录制中的群消息 SHALL 全部入档，不因其没有文字段而被跳过：纯图片、纯 @、贴纸等消息 MUST 与普通文本消息一样写入 `messages.jsonl`。插件匹配 MUST 在「无文字」时回落到「本群是否正在录制」的判断，而不是直接判定不匹配。非录制状态与未知的 `/跑团` 子命令行为 MUST 保持不变。

#### Scenario: 只发图片
- **WHEN** 录制中玩家只发一张图片、不配文字
- **THEN** 图片保存进 `imgs/` 并写入记录，网页按图片气泡显示

#### Scenario: 只发 @
- **WHEN** 录制中玩家只 @ 某人
- **THEN** 该消息带 @ 段写入记录

#### Scenario: 未在录制
- **WHEN** 群里没有录制时有人只发图片
- **THEN** 插件不匹配、不产生任何记录文件

#### Scenario: 未知子命令
- **WHEN** 录制中有人发送 `/跑团 乱打`
- **THEN** 插件仍不匹配（保持原有行为）
