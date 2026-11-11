# COC 技能名校验与去重 — 验收记录

实施分支：`master`；版本 1.71.4。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 规范化行为 | `node test/test_trpg_coc_skill_name.js` 9 项全过：官方名、别名归一、`科学:生物学`、全角冒号、漏分隔符补全、空白裁剪；纯类别与凭空造名返回 null | 通过 |
| AC02 录入拦截 | `addSkill` 调用 `normalizeSkillName`，失败提示「无法识别的技能名」；列表内按 `canonSkill` 比较，已存在提示「技能已存在」。浏览器手测待确认 | 代码层通过 |
| AC03 数据源 | `check_trpg_coc_api.py` 全过，含新增「技能别名表」断言（`侦查 → 侦察`） | 通过 |
| AC04 文档与归档 | 全量 `pytest` → **689 passed**（4:49）；`openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.71.4]` 与 `BOTERO_VERSION = "1.71.4"` 一致 | 通过 |

## 实测与裁定

- **根因**：服务端 `skill_name_ok()` 已经定义了合法集合（官方 39 项 + 类别前缀），但它只在 `finalize()` 里被用来**静默跳过**，从未回传给页面；前端于是成了唯一入口却毫无约束。
- **测试方式**：`test_trpg_coc_skill_name.js` 从 `trpg_coc.js` 里截取 `canonSkill`/`normalizeSkillName` 两个函数直接执行，而不是复制一份规则进测试，避免规则漂移。
- **前端比服务端严格一档**：服务端 `startswith("科学")` 会接受纯类别名「科学」，前端拒绝（没有专攻名时无意义）；老数据仍能正常渲染。
- **未做（原方案里的「半条 B」）**：保存响应不回传被忽略的技能名。选项是 A 而非 A+B，故未实现。
