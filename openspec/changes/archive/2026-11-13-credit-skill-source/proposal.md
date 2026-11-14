# 信用评级改为技能表加点，资产区只同步

## Why

1.93.0 把信用评级做成了「资产区唯一来源」，但按规则它的值来自技能点：职业规定了信用评级的上下限，**先**用职业点补到下限，**之后**才允许用兴趣点继续加。资产栏随便填一个数既不符合规则，也绕过了职业点预算。

## What Changes

- `core/trpg/coc.py`：
  - `credit_entry()` / `credit_value()`：信用评级 = 技能行里的「职业点 + 兴趣点」（基础值恒为 0，成长标记按规则不打）。
  - `normalize_credit_rating()`：保存时规整——基础值清零、成长并入职业点；技能行合计为 0 而资产区仍有历史值时按下限迁移（下限以内记职业点，其余记兴趣点；没有职业则全记兴趣点）；最后把 `credit_rating` 写成技能合计，供资产参考表与生活水平继续使用。
  - `credit_problems()`：新增两条规则校验——合计必须落在职业区间内；未到下限时不能有职业点以外的加点（「信用评级未到职业下限 35 时只能用职业点加点」）。
  - `occupational_point_problems()`：信用评级对所有职业都算本职技能，用职业点加点不再被拒。
- 建卡页 `trpg_coc.js`：技能表的信用评级行「基础 / 成长」只读、「职业 / 兴趣」可编辑（带悬停说明）；资产区的信用评级输入改为 `readonly`，随技能行实时同步；选职业时若信用评级还是 0，自动把职业下限填进职业点列。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：信用评级的数据来源与加点规则（取代 1.93.0 的「资产区唯一来源」）。

## Scope and Compatibility

- 旧卡：资产区有值、技能行没点数时，保存会按下限迁移成「职业点 + 兴趣点」，不丢数值。
- 资产参考表、生活水平、`.ra 信用评级`、快照都读同一个合计值。
- 无数据库变更；版本 1.94.0。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 职业点 | `python -m pytest test/test_trpg_coc.py -q -k CreditSkillSource` | 职业点 40（药剂师下限 35）→ 校验通过、`skill_value` 40、`credit_rating` 同步 40 |
| AC02 兴趣点在上限内 | 同上 | 职业 35 + 兴趣 10 → 45，校验通过 |
| AC03 下限前禁止兴趣点 | 同上 | 只有兴趣 40、或职业 30 + 兴趣 5 → 报「只能用职业点加点」 |
| AC04 区间 | 同上 | 职业 20（低于下限）、职业 35 + 兴趣 50（超上限）→ 报「信用评级应在 35-75 之间」 |
| AC05 旧卡迁移 | 同上 | 资产区 45、技能行空 → 迁移成职业 35 + 兴趣 10，`credit_rating` 45 |
| AC06 基础与成长 | 同上 | `base: 30, growth: 5` 被规整为 0，成长并入职业点 |
| AC07 职业点不拒 | 同上 | `occupational_point_problems` 对信用评级返回空 |
| AC08 骰子 | `python -m pytest test/test_trpg.py -q -k credit` | `.ra 信用评级` 输出 `[信用评级=40]`，不打成长标记 |
| AC09 接口 | `python test/scripts/check_trpg_coc_api.py` | 职业点建卡 200 且资产区同步；下限后用兴趣点 200；下限前用兴趣点 400；超上限 400；旧卡迁移正确 |
| AC10 页面 | `python -m pytest test/test_trpg_coc.py -q -k CreditSkillUi` | 技能行可编辑带说明；资产区输入 `readonly` 并随技能行同步 |
| AC11 全量回归 | `python -m pytest -q` | 全绿 |
| AC12 文档与归档 | `openspec validate coc-character-sheet --strict`；归档与实现同一 commit | `CHANGELOG [1.94.0]` 与 `BOTERO_VERSION` 一致 |
