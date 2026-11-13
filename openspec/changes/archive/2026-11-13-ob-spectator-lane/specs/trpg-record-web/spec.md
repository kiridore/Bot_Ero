# trpg-record-web — 变更（观战席）

## ADDED Requirements

### Requirement: 观察者消息渲染为观战席细条
`role` 为 `ob` 的用户消息 SHALL 渲染为观战席样式：MUST NOT 显示头像与气泡底框，MUST 由「眼睛标记 + 群昵称 + 时间 + 正文」组成，正文在剩余宽度内换行（悬挂缩进）。观察者的图片 SHALL 保留灯箱能力并缩小显示；观察者的暗骰 SHALL 带「暗骰」小标签；整句括号的观察者发言 SHALL 仍受「隐藏场外发言」开关控制。观察者自己查看时该细条 SHALL 右对齐。DM 与其他玩家 MUST 保持既有气泡样式。

#### Scenario: 观察者发言
- **WHEN** 观察者在记录里发一条文字
- **THEN** 显示为一条灰色细线（眼睛 · 昵称 · 时间 · 正文），没有头像与气泡

#### Scenario: 观察者发图
- **WHEN** 观察者发图片
- **THEN** 图片在细条内以缩略尺寸显示，点击仍可放大

#### Scenario: 观察者暗骰
- **WHEN** 观察者使用 `.rh`
- **THEN** 细条上出现「暗骰」小标签

#### Scenario: DM
- **WHEN** DM 发言
- **THEN** 仍是正常气泡
