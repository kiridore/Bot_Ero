# trpg-record-web — 变更（两态）

## MODIFIED Requirements

### Requirement: 记录状态判定
每条记录 SHALL 由文件推断状态并只展示两态：`meta.json.end` 为 null 且存在 `messages.jsonl` 时为「录制中」；`end` 有值时为「已结束」。本能力 MUST NOT 引入「已结束·未导出」「已导出」等按 `record.md` 区分状态的展示，MUST NOT 依据"最新消息时间"追加「（可能已中断）」之类提示。记录状态的恢复与自动终止由 `trpg-recording-recovery` 负责，网页只读取磁盘结果，MUST NOT 自行改写或删除数据。

#### Scenario: 残留录制
- **WHEN** 存在 `end` 为 null 且最新消息时间为 30 分钟前的记录
- **THEN** 列表与详情页显示「录制中」，不附加「（可能已中断）」之类的提示

#### Scenario: 已结束记录
- **WHEN** 记录的 `meta.json.end` 有值（无论是否存在 `record.md`）
- **THEN** 列表与详情页都显示「已结束」

#### Scenario: 录制中的记录
- **WHEN** 记录的 `meta.json.end` 为 null
- **THEN** 列表与详情页显示「录制中」，不附加任何"可能已中断"提示（即使最新消息是很久以前）
