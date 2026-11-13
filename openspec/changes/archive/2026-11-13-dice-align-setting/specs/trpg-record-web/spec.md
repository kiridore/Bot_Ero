# trpg-record-web — 变更（骰子结果对齐）

## ADDED Requirements

### Requirement: 骰子结果对齐方式可切换
记录详情页 SHALL 提供骰子结果（机器人消息）对齐切换：左、居中、右三种，默认居中。切换控件 SHOULD 位于右下角悬浮按钮组，点击按「左 → 中 → 右」循环，按钮图标与可读标签 MUST 反映当前状态。选择 SHALL 存入 `localStorage` 并在下次打开时恢复；存量值非法时 MUST 回落居中。对齐 MUST 只影响机器人消息，玩家与观战席的排版不受影响。

#### Scenario: 默认
- **WHEN** 首次打开记录页
- **THEN** 骰子结果居中显示

#### Scenario: 切到左对齐
- **WHEN** 点击对齐按钮直到进入左对齐
- **THEN** 骰子结果靠左，按钮图标变为左对齐图标，刷新后保持

#### Scenario: 非法存档
- **WHEN** `localStorage` 里的值不是 left/center/right
- **THEN** 按居中渲染并写回 `center`
