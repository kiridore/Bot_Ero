# trpg-record-web — 变更（气泡收缩）

## ADDED Requirements

### Requirement: 气泡按内容收缩
消息气泡的宽度 SHALL 由内容决定，MUST NOT 因为名字行更宽而被拉长。消息容器 SHALL 为列向弹性布局、子项按内容对齐（他人靠左、自己靠右、机器人居中），气泡最大宽度不得超过容器。

#### Scenario: 短消息
- **WHEN** 玩家只发「嗯」
- **THEN** 气泡只有「嗯」那么宽，而不是与上方名字行等宽

#### Scenario: 长消息
- **WHEN** 玩家发送一段长文本
- **THEN** 气泡在 78%（机器人 86%）宽度上限内换行，不溢出
