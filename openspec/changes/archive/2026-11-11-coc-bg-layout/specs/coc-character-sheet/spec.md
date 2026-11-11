# coc-character-sheet — 变更（背景区布局）

## ADDED Requirements

### Requirement: 背景区布局
建卡页背景区 SHALL 使用独立的两列网格（宽屏一行两个，≤640px 时回落单列）；背景文本框 SHALL 最小高度 5.5rem、行高 1.5 且可垂直拖拽拉伸；调查员笔记 SHALL 提供至少 4 行高度。

#### Scenario: 宽屏填写背景
- **WHEN** 用户在宽屏打开 `/trpg/coc`
- **THEN** 个人描述、思想与信念等背景项每行显示两个，文本框高度足够显示两行以上文字

#### Scenario: 窄屏
- **WHEN** 视口宽度 ≤640px
- **THEN** 背景项改为单列，输入框铺满可用宽度
