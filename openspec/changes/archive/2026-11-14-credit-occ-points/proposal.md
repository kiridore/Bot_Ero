# 信用评级可以用职业点加点（前后端规则对齐）

## Why

1.94.0 在服务端放开了「信用评级可以用职业点加点」（它对所有职业都算本职技能），但建卡页没跟上：

1. `occAllows()` 只认职业的 `required` 与已选池，而 113 个职业的 `required` 里都没有「信用评级」→ 该行的「职业」输入框被 `disabled` 并提示「非本职技能，只能用兴趣点」，玩家根本填不进去。
2. `fillCreditFloor()` 的守卫是「技能行合计为 0 才补」，所以先填了兴趣点再选职业时不会补，职业点永远是 0。
3. 属性还没掷时职业点预算是 0，即使填了也只会看到「职业点超出 35/0」，没有说明原因。

## What Changes

- `occAllows()`：`信用评级` 恒为允许（所有职业的本职技能），职业列不再被禁用、也不会被「清理非本职技能职业点」逻辑清零。
- `fillCreditFloor()`：只要还没分配过职业点就补，且**保住玩家已填的合计**——合计低于下限时按下限托底，高于下限时只把下限那部分挪进职业点（例如先填兴趣 50、下限 35 → 职业 35 + 兴趣 15）。
- 职业点预算为 0 且有职业点时，提示改为「职业点上限是 0：先把属性（教育等）填出来，职业点才有地方扣」。
- `test/test_trpg_coc_credit_fill.js` 增加 6 项断言（先填兴趣点、超出下限、职业点放行、其他技能仍被拦等）。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：信用评级的职业点可用性与自动填充口径。

## Scope and Compatibility

- 只改前端可用性与预填；服务端 `credit_problems()` 早已按同一规则校验。
- 其他技能的「非本职技能不能加职业点」行为不变。
- 无数据库变更；版本 1.96.3。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 职业点放行 | `node test/test_trpg_coc_credit_fill.js` | `occAllows({}, "信用评级")` 为 true；`occAllows({}, "攀爬")` 仍为 false |
| AC02 先填兴趣点再选职业 | 同上 | 兴趣 20 + 选药剂师（下限 35）→ 职业 35、兴趣 0、资产 35 |
| AC03 保住玩家合计 | 同上 | 兴趣 50 + 下限 35 → 职业 35、兴趣 15、资产 50 |
| AC04 已分配职业点不动 | 同上 | 职业 40 → 换职业仍是 40 |
| AC05 预算提示 | `python -m pytest test/test_trpg_coc.py -q -k CreditSkillUi` 或源码守卫 | 源码含「职业点上限是 0：先把属性（教育等）填出来」 |
| AC06 全量回归 | `python -m pytest -q` | 全绿 |
| AC07 文档与归档 | `openspec validate coc-character-sheet --strict`；归档与实现同一 commit | `CHANGELOG [1.96.3]` 与 `BOTERO_VERSION` 一致 |
