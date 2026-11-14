# 职业选择：下拉 + 打字搜索

## Why

职业是 113 项的下拉框，想选「潜水员」要先滚过一长串；而职业名和点数据公式、信用评级区间、本职技能全都绑在这个选择上，输入框又不能随便放行。

## What Changes

- 建卡页职业字段从 `<select>` 改为 `<input list="occOptions">` + `<datalist>`：点箭头可以下拉，直接打字可以按前缀/包含搜索（浏览器原生行为），选中后与原来的下拉等价。
- `currentOccupation()` 改为按名字**精确匹配**职业表；新增 `unknownOccupation()`：输入了一半或打错时返回该文本。
- 换职业的处理只在「真的换成了另一个职业」时清空可选池、补本职技能；打了字但没匹配到职业时不动作，已选内容不会被清掉。
- 保存前拦一道：职业名不在列表里时提示「职业「xxx」不在列表里：请从下拉里选一个，或清空」，不静默当成「未选职业」。
- `collect()` 提交前裁掉职业名的首尾空白。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：职业选择的交互与校验。

## Scope and Compatibility

- 数据不变：提交的仍是职业名字符串；服务端仍按名字查职业模板。
- 浏览器的 datalist 支持度差异只影响「候选怎么显示」，不影响选中与保存。
- 无数据库变更；版本 1.96.1。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 控件 | `python -m pytest test/test_trpg_coc.py -q -k OccupationSearch` | 源码含 `id="occupation"`、`list="occOptions"`、`<datalist id="occOptions">`，不含 `<select id="occupation">` |
| AC02 精确匹配 | 同上 | 含 `unknownOccupation` 且按 `o.name === name` 匹配 |
| AC03 保存拦截 | 同上 | 保存前调用 `unknownOccupation()`，提示「不在列表里」 |
| AC04 只在真换职业时重置 | 同上 | 含 `if (occ.name === lastOccupation) return;` |
| AC05 全量回归 | `python -m pytest -q`；全部 `test_trpg_coc*.js` | 全绿 |
| AC06 文档与归档 | `openspec validate coc-character-sheet --strict`；归档与实现同一 commit | `CHANGELOG [1.96.1]` 与 `BOTERO_VERSION` 一致 |
