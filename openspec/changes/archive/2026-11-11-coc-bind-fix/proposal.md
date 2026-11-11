# 修复 COC 建卡页 skillInput 未定义导致整页报错

## Why

1.73.3 把「添加技能」改成页面内输入时，只落下了两行事件绑定（`skillInput.addEventListener`），对应的 `const skillInput`、`const setSkillHint`、`function addSkillFromInput()` 没有写进文件。`node --check` 只校验语法，查不出未声明标识符，于是整页在 `bind()` 阶段抛 `skillInput is not defined`，建卡页完全打不开。

## What Changes

- 补上 `skillInput` / `skillHint` / `setSkillHint` / `addSkillFromInput()` 的定义，放在事件绑定之前。
- 新增运行时守卫测试 `test/test_trpg_coc_bind_runtime.js`：用 Proxy 沙箱实际执行 `bind()`，捕获「标识符未定义 / 不是函数」这类 `node --check` 查不出的运行时错误。
- 补两条源码守卫断言（定义必须存在）。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：建卡页脚本的可执行性（无新增需求项，仅修复实现缺陷）。

## Scope and Compatibility

- 仅补回丢失的定义，不改交互行为。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 页面可打开 | `node test/test_trpg_coc_bind_runtime.js` | `bind()` 在沙箱中可执行，无未定义标识符 |
| AC02 回归守卫 | 删掉 `const skillInput` 后重跑同一脚本 | 脚本以非零码失败，说明能捕获该缺陷 |
| AC03 行为不变 | `python -m pytest test/test_trpg_coc.py -q` | 33 例通过，含新增定义断言 |
| AC04 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿；`CHANGELOG [1.73.4]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
