# 属性合计（不含幸运）

## Why

跑团里常要看调查员的属性总量（八项主属性之和），用来快速判断这张卡是「偏科」还是「全能」。现在只能自己心算，而且幸运不属于主机能，算进去会虚高。

## What Changes

- 建卡页属性区下方新增一行「属性合计（不含幸运）」，随属性输入实时刷新（`#out-attr-sum`，在 `rerenderDerived()` 里用 `attr(key)` 汇总八项）。
- 角色卡查看页的属性区块下方新增同样一行，数值取自服务端 `finalize()` 给出的 `scores`（不含幸运）。
- 样式 `.coc-attr-sum`（灰字 + 数字加粗等宽）。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：属性区块的展示信息。

## Scope and Compatibility

- 纯展示，不参与任何规则计算，也不写库。
- 幸运不计入；年龄调整后的属性值按当前卡片值汇总（与界面显示一致）。
- 无数据库变更；版本 1.98.0。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 编辑页 | `python -m pytest test/test_trpg_coc.py -q -k attr_sum` | 源码含 `id="out-attr-sum"` 与 `.filter(([key]) => key !== "luck")` |
| AC02 查看页 | `node test/test_trpg_coc_view_dom.js` | 渲染结果含「属性合计（不含幸运）」与八项之和（样例卡 470） |
| AC03 不含幸运 | 同上 | 合计不等于「含幸运」的数值（520） |
| AC04 全量回归 | `python -m pytest -q` | 全绿 |
| AC05 文档与归档 | `openspec validate coc-character-sheet --strict`；归档与实现同一 commit | `CHANGELOG [1.98.0]` 与 `BOTERO_VERSION` 一致 |
