# trpg-record-web — 变更（悬浮按钮）

## ADDED Requirements

### Requirement: 记录页悬浮操作按钮
记录详情页 SHALL 在页面底部固定显示三个圆形按钮：回到顶部、隐藏暗骰、隐藏场外发言。按钮 MUST 只用图标（来自 `/shared/icons.js`），并带 `title` 与 `aria-label`；两个切换按钮 SHALL 用 `aria-pressed` 反映状态。悬浮按钮与页头勾选框 MUST 共用同一份状态，任一处切换后另一处同步。回到顶部按钮 SHALL 平滑滚动到页首。

#### Scenario: 回到顶部
- **WHEN** 点击底部第一个按钮
- **THEN** 页面滚动到顶部

#### Scenario: 隐藏暗骰
- **WHEN** 点击「隐藏暗骰」按钮（默认已按下 = 暗骰隐藏）
- **THEN** 暗骰消息显示/隐藏切换，页头「显示暗骰」勾选同步，按钮 `aria-pressed` 同步

#### Scenario: 隐藏场外发言
- **WHEN** 点击「隐藏场外发言」按钮
- **THEN** 场外气泡隐藏/显示切换，页头勾选与 `localStorage` 同步

#### Scenario: 图标
- **WHEN** 页面加载
- **THEN** 三个按钮分别显示向上箭头、划掉的眼睛、划掉的气泡图标，不出现纯文本标签
