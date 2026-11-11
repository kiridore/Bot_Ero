# coc-character-sheet — 变更（脚本运行时守卫）

## ADDED Requirements

### Requirement: 建卡页脚本运行时守卫
建卡页脚本 SHALL 能在无未定义标识符的情况下执行 `bind()`；测试 MUST 以真实执行方式（而非仅语法检查）验证该点，且在缺失声明时失败。

#### Scenario: 绑定阶段无未定义标识符
- **WHEN** 运行 `node test/test_trpg_coc_bind_runtime.js`
- **THEN** `bind()` 在沙箱中执行成功，输出「bind() 可执行且所有标识符已定义」

#### Scenario: 缺失声明能被捕获
- **WHEN** 删除 `const skillInput = ...` 后再运行该脚本
- **THEN** 脚本以非零退出码失败
