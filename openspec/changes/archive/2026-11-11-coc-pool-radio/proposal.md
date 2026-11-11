# 可选池控件改为「单选用 radio、多选用 checkbox」并弱化未选满提示

## Why

1.73 把全部具名池都渲染成复选框，但「选 1 项」的池（如「一项社交技能」）用复选框既不符合交互语义，也允许用户勾出两个互相排斥的选项（保存时才被 400 拒绝）。另外未选满/超选提示沿用灰色小字，玩家容易忽略。

## What Changes

- 具名池按 `count` 选择控件类型：`count === 1` 用 `radio`（同池同名互斥），`count > 1` 用 `checkbox`。
- 提示行同时报告不足与超出：「可选 #N 还差 M 项」「可选 #N 多选了 M 项」。
- 提示行改为低饱和红（`color-mix(in srgb, var(--red) 62%, var(--ink-soft))`），且无提示时隐藏，避免整块常驻。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：可选池控件的控件类型与提示样式。

## Scope and Compatibility

- 只改建卡页控件与样式，不动数据结构、校验规则与接口。
- 校验仍在服务端（页面提示不替代 400）。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 单选池 | `python -m pytest test/test_trpg_coc.py -q -k pool_single_choice` | 源码守卫断言 `choice.count === 1` 决定 `radio` |
| AC02 提示逻辑 | 同上 `-k choice_warning` | 提示包含「多选了」与 `coc-choice-warn-on` 类 |
| AC03 样式 | 人工看 `/trpg/coc` | 选药剂师后「选择社交技能」为单选圆点；未选满时提示为低饱和红，选满后消失 |
| AC04 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿；`CHANGELOG [1.73.1]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
