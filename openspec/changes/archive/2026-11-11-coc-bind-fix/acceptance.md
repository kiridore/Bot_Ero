# 修复 skillInput 未定义 — 验收记录

实施分支：`master`；版本 1.73.4。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 页面可打开 | `node test/test_trpg_coc_bind_runtime.js` → `ok - bind() 可执行且所有标识符已定义` | 通过 |
| AC02 回归守卫 | 临时删除 `const skillInput = ...` 后重跑该脚本 → `FAIL - bind() 可执行且所有标识符已定义 skillInput.addEventListener is not a function`，退出码 1；随后从备份恢复 | 通过（已验证能捕获） |
| AC03 行为不变 | `test_trpg_coc.py` 33 例通过（含新增的 4 条定义存在性断言） | 通过 |
| AC04 文档与归档 | 全量 `pytest` → **724 passed**（4:50）；`openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.73.4]` 与 `BOTERO_VERSION = "1.73.4"` 一致 | 通过 |

## 根因与教训

- **根因**：1.73.3 的编辑用字符串替换插入事件绑定，但配套的 `const skillInput` / `setSkillHint` / `addSkillFromInput` 未同时落地；`node --check` 只做语法检查，未声明标识符在运行时才炸，于是整个 `bind()` 抛错、页面白屏。
- **守卫**：新增 `test/test_trpg_coc_bind_runtime.js`，用 Proxy 作为未声明标识符的兜底，在 `vm` 里真实执行 `bind()`；缺失声明会以 `xxx is not a function` 失败。
- **局限**：该沙箱只覆盖 `bind()` 区块；`render()` / `init()` 的运行时错误仍需浏览器手测或后续扩展沙箱范围。
