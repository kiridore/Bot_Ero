# coc-character-sheet — 变更（资产区信用评级只读展示）

## ADDED Requirements

### Requirement: 资产区信用评级只读展示
资产区的信用评级 MUST 以只读文本（`<output>`）呈现，MUST NOT 提供可编辑的输入框或数字步进控件；其值 SHALL 始终来自技能表「信用评级」行的合计。点击「按规则填入」与资产提示 SHALL 使用同一来源，MUST NOT 回读该展示元素。生活水平 SHALL 在尚未选择时跟随信用评级档位，玩家已选择后 MUST NOT 被覆盖。

#### Scenario: 技能表改动
- **WHEN** 玩家把信用评级的职业点改成 40
- **THEN** 资产区显示 40，且该处没有任何可输入的控件

#### Scenario: 生活水平已手动选择
- **WHEN** 玩家把生活水平选成「小康」，随后提高信用评级
- **THEN** 生活水平保持「小康」，下方提示说明与信用评级对应的档位差异
