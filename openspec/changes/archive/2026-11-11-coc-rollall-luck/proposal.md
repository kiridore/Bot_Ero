# 修复「全部重掷」漏掉幸运

## Why

COC 建卡页的「属性」区块里，幸运与八项属性同属一组、规格同为 3d6×5，但「全部重掷」只遍历 `ATTRS`（八项），幸运不在其中——按钮文案承诺「全部」却少了第 9 项，属于实现遗漏而非设计。

## What Changes

- 「全部重掷」补上幸运：按 `3d6`（×5）重掷 `luck`。
- 删除死代码 `rollDieReady()`（只是 `rollDie()` 的别名，幸运单独走了一条路径）。
- 新增两条源码守卫测试：`rollAll` 分支必须覆盖幸运、脚本中不得再出现 `rollDieReady`。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：明确「全部重掷」覆盖幸运。

## Scope and Compatibility

- 只改建卡页脚本与一条测试，不动接口、校验与数据结构。
- 幸运仍是 0–99 的独立字段，不参与职业点/兴趣点预算。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 覆盖幸运 | `python -m pytest test/test_trpg_coc.py -q` | `rollAll` 处理块包含 `luck` 且按 `3d6` 重掷；脚本中不含 `rollDieReady` |
| AC02 语法 | `node --check webapp/static/trpg_coc.js` | 通过 |
| AC03 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿；`CHANGELOG [1.71.2]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
| AC04 真实环境冒烟 | 部署机手工 | 打开 `/trpg/coc`，点「全部重掷」后九项（含幸运）全部变化且落在 15–90 |
