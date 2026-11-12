# `/跑团 角色 查看` 按规则输出

## Why

`/跑团 角色 查看` 固定调用 DND 的 `format_sheet`，调查员卡也被渲染成 DND 格式（等级、熟练加值、豁免…），而 COC 的卡片文本（`core/trpg/coc.py::format_sheet`：属性、HP/MP/SAN、伤害加值、技能、武器、随身物品、资产）从来没被用上。`/跑团 角色 列表` 早就按规则区分了，查看没跟上。

## What Changes

- `plugins/trpg_char`：新增 `format_card(char_data)`，按 `rules` 选择 COC 或 DND 的卡片文本；`_handle_view` 改用它。
- 缺 `rules` 的旧卡仍走 DND（与其余代码一致）。

## Capabilities

### New Capabilities

- `trpg-character-card`：`/跑团 角色` 子指令的输出口径。

## Scope and Compatibility

- 只改查看输出；列表、切换、删除的文案不变。
- 调查员卡不再显示「Lv.」「熟练加值」这类 DND 字段；DND 卡输出逐字不变。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 COC 卡 | `python -m pytest test/test_trpg_char.py -q -k ViewByRules` | 含「HP」「伤害加值」「药剂师」，不含「Lv.」「熟练加值」 |
| AC02 DND 卡 | 同上 | 含「Lv.」，不含「伤害加值」 |
| AC03 旧卡 | 同上 | 没有 `rules` 字段时按 DND 输出 |
| AC04 文档与归档 | `python -m pytest -q`；`openspec validate trpg-character-card --strict` | 全量回归绿；`CHANGELOG [1.81.2]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
