# trpg-character-card Specification

## Purpose
定义 `/跑团 角色` 子指令的文案口径：列表与查看都必须按角色卡所属规则输出，不能把调查员卡渲染成龙与地下城格式。

## Requirements

### Requirement: 查看按规则渲染
`/跑团 角色 查看` SHALL 依据角色卡 `rules` 选择卡片文本：`coc7th` 使用调查员卡格式（属性、HP/MP/SAN、伤害加值、体格、闪避、技能、武器、随身物品、资产），`dnd5e` 使用原有格式。缺少 `rules` 时 SHALL 按 `dnd5e` 处理。

#### Scenario: 调查员卡
- **WHEN** 当前角色是 COC 卡并发送 `/跑团 角色 查看`
- **THEN** 输出包含 HP/MP/SAN、伤害加值、职业等调查员字段，不出现「Lv.」「熟练加值」

#### Scenario: 龙与地下城卡
- **WHEN** 当前角色是 DND 卡
- **THEN** 输出与原行为一致（等级、种族、职业、AC、豁免等）

#### Scenario: 旧卡
- **WHEN** 卡上没有 `rules` 字段
- **THEN** 按 DND 格式输出
