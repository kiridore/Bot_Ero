# 「全部重掷」覆盖幸运 — 验收记录

实施分支：`master`；版本 1.71.2。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 覆盖幸运 | `test_trpg_coc.py::TestBuilderScript` 2 例通过：`rollAll` 处理块含 `luck` 且按 `3d6` 重掷；脚本中 `rollDieReady` 出现 0 次 | 通过 |
| AC02 语法 | `node --check webapp/static/trpg_coc.js` 通过 | 通过 |
| AC03 文档与归档 | 全量 `pytest` → **688 passed**（4:42）；`openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.71.2]` 与 `BOTERO_VERSION = "1.71.2"` 一致 | 通过 |
| AC04 真实环境冒烟 | 待所有者：`/trpg/coc` 点「全部重掷」，确认九项全部变化且落在 15–90 | 未执行 |

## 实测与裁定

- **根因**：`ATTRS` 常量只有八项属性，幸运是单独写的一行 HTML，`rollAll` 只遍历 `ATTRS`；`rollDieReady()` 这个转发别名说明幸运当初是后加的、没并入统一循环。
- **守卫方式**：该页面没有 DOM 测试桩，本次用源码断言守住「rollAll 必须包含 luck」，成本低且能挡住同类回归；如需行为级测试，需要为 500 行建卡页搭 DOM stub，另立项。
- **未改**：幸运仍是 0–99 独立字段，不参与职业点/兴趣点预算，也不影响 SAN 上限。
