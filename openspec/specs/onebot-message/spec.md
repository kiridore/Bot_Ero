# onebot-message Specification

## Purpose
定义入站消息的格式归一化：无论后端把 `message` 下发成消息段数组还是 CQ 码字符串，插件都只面对消息段列表。

## Requirements

### Requirement: 消息格式归一化
`Event.message` SHALL 始终返回消息段列表。当原始 `message` 是字符串（CQ 码格式）时，MUST 按上游规范解析出各消息段，并按规则反转义文本（`&amp;`→`&`、`&#91;`→`[`、`&#93;`→`]`，CQ 参数内额外 `&#44;`→`,`）；当原始 `message` 是数组时 MUST 原样返回，不做任何改写。

#### Scenario: 数组格式
- **WHEN** 事件里 `message` 是 `[{"type":"text","data":{"text":"hi"}}]`
- **THEN** `Event.message` 返回同一个列表对象

#### Scenario: 字符串格式
- **WHEN** 事件里 `message` 是 `。hp 满 [CQ:at,qq=100000002]`
- **THEN** `Event.message` 返回 `[{text}, {at, qq=100000002}]`

#### Scenario: 转义
- **WHEN** 字符串里包含 `&#91;x&#93; &amp;data`
- **THEN** 解析出的文本为 `[x] &data`

#### Scenario: 参数内逗号
- **WHEN** CQ 参数值里出现 `&#44;`
- **THEN** 该参数还原为逗号，且不会被当成参数分隔符
