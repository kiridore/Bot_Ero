# trpg-record-web — 变更（暂停态）

## ADDED Requirements

### Requirement: 三态徽标
记录状态 SHALL 为 `recording` / `paused` / `ended` 三态。`meta.end` 为空且 `meta.paused` 为真时状态 MUST 为 `paused`，列表与详情显示「已暂停」，列表的时间行显示「— 已暂停」。详情页在 `paused` 态下 SHALL 继续轮询，使恢复后的徽标自动变回「录制中」。

#### Scenario: 暂停态列表
- **WHEN** 列表里有暂停中的记录
- **THEN** 该行徽标为「已暂停」，时间行显示「已暂停」

#### Scenario: 暂停态详情
- **WHEN** 打开暂停中的记录
- **THEN** 详情页徽标为「已暂停」，并继续轮询状态
