# COC 本职技能可选池的显式选择

## Why

1.72 只校验「职业点加在固定项或池内、不超配额」，卡片**不记录玩家从池里选了哪几项**。于是「一项社交技能（魅惑、话术、恐吓、说服）」可以只在「魅惑」上加职业点、另一项 0 点也算合法——池只是上限，不是选择。

所有者要求改成真正的显式选择（且确认生产没有旧卡，不需要兼容）。

## What Changes

- 卡片新增 `occupation_choices`：`{"池下标": ["技能名", …]}`，与职业定义的 `choices` 顺序一一对应。
- 校验分两层：
  - `occupation_choice_problems()`：选择本身是否合法——技能名必须在技能表内、必须落在该池（具名池精确匹配 / `类别:*` 按前缀 / `*` 任意）、数量不超 `count`；
  - `occupational_point_problems()`：职业点只能加在固定项或**已被选中**的池内技能上。
- 未选满不阻止保存：`occupation_choice_warnings()` 返回「可选 #N 还差 M 项」，页面显示为提示。
- 建卡页在职业区下方按池渲染控件：具名池用多选框，`类别:*` / `*` 池用文本输入（`技艺:烹饪` 这类写法）。
- 选定池内技能若技能表里还没有该行，页面自动补一行（基础值取技能表默认）。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：本职技能可选池的显式选择与校验。

## Scope and Compatibility

- 不兼容旧卡（所有者确认生产无旧卡）：没有 `occupation_choices` 的卡若能加职业点，需要重新选择。
- 兴趣点不受影响（兴趣点可加在任意技能）。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 选择校验 | `python -m pytest test/test_trpg_coc_occupations.py -q` | 池外选择、表外技能名、未知池下标、超配额均报错；合法选择通过 |
| AC02 归属校验 | 同上 | 固定项可直接加点；池内技能必须先被选中才能加点；未选中的池内技能加点被拒 |
| AC03 未选满提示 | 同上 | `occupation_choice_warnings()` 对未选满的池返回「还差 N 项」，选满后为空；不阻止 `validate()` 通过 |
| AC04 接口 | `python test/scripts/check_trpg_coc_api.py` | 选择随卡片回传；未选入池即加点 400；池外选择 400；超选 400 |
| AC05 页面 | 人工看 `/trpg/coc` | 具名池显示多选、`类别:*`/`*` 池显示输入框；选定后自动补技能行；未选满显示提示 |
| AC06 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿；`CHANGELOG [1.73.0]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
