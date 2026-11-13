# trpg-record-web — 变更（场外发言开关）

## ADDED Requirements

### Requirement: 场外发言识别与隐藏开关
记录详情页 SHALL 识别场外发言：整条消息只含文本段、去掉首尾空白后被半角或全角括号完全包裹、且括号内非空。页面 MUST 提供「隐藏场外发言」开关，勾选后在客户端隐藏这些消息；开关状态 SHALL 记在 `localStorage`，刷新后保持。默认 MUST 为不隐藏。切换 MUST NOT 重新请求接口。

#### Scenario: 识别场外
- **WHEN** 某条消息文本为 `（我去倒杯水）` 或 `(等下)`
- **THEN** 该消息带 `is-ooc` 标记

#### Scenario: 不是场外
- **WHEN** 文本为 `（笑）他推门进来`、`（）`，或消息里含图片
- **THEN** 不标记为场外

#### Scenario: 开关
- **WHEN** 勾选「隐藏场外发言」
- **THEN** 场外消息立刻隐藏，刷新页面后仍隐藏；取消勾选后重新显示
