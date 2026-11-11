# 非本职技能行的职业点列禁用

## Why

1.72/1.73 只做了服务端校验：把职业点加在非本职技能上时保存返回 400。但页面把「职业」列渲染在**每一行**且始终可编辑，玩家会以为可以用，填完一屏才在保存时被整体拒绝——一次只报一条，要反复改、反复存。

## What Changes

- 新增纯函数 `occAllowedNames(occ, choices)`：返回可加职业点的技能集合（固定项含 `类别:*` 通配 + `occupation_choices` 里已选中的技能）；`occAllows()` 做匹配。
- 每次重算派生值时同步刷新技能表：非本职行的「职业」输入框 `disabled`、整行加 `is-not-occ` 淡灰、输入框 tooltip「非本职技能，只能用兴趣点」。
- 若某行因移出可选池/更换职业而变得不可加点且已有数值，则清零并提示「已清除职业点：X（不是本职技能）」。
- 兴趣点列不受限制。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：技能表职业点列的可编辑范围。

## Scope and Compatibility

- 只改建卡页行为与样式，服务端校验不变（仍是最终裁决）。
- 不用兼容旧卡（生产无旧卡）；若存在越界数值，会在重算时被清零并提示。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 允许集合 | `node test/test_trpg_coc_skill_name.js` | 固定项、`类别:*` 通配、已选池内技能可加点；未选中的自由技能不可；别名按规范名匹配；无职业时为空 |
| AC02 行禁用 | `python -m pytest test/test_trpg_coc.py -q -k non_occ` | 源码含 `occInput.disabled = !allowed`、`is-not-occ` 与 `[data-occ]:disabled` 样式 |
| AC03 视觉 | 人工看 `/trpg/coc` | 药剂师卡里「攀爬」的职业列灰掉不可输入，兴趣列仍可编辑；把「攀爬」选进自由池后立即可输入 |
| AC04 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿；`CHANGELOG [1.73.2]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
