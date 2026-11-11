# 添加技能就地输入 — 验收记录

实施分支：`master`；版本 1.73.3。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 无弹窗 | `test_trpg_coc.py::test_add_skill_uses_inline_input` 通过：脚本中 `prompt(` 出现 0 次；存在 `id="skillName"`、`list="skillOptions"`、`addSkillFromInput` | 通过 |
| AC02 交互 | 输入框绑定 `datalist`（39 个官方技能名）、按钮与回车都调用 `addSkillFromInput()`；失败走 `setSkillHint`（就地提示、保留输入），成功后清空并 `focus()` | 代码层通过，浏览器手测待确认 |
| AC03 文档与归档 | 全量 `pytest` → **723 passed**（4:48）；`openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.73.3]` 与 `BOTERO_VERSION = "1.73.3"` 一致 | 通过 |

## 实测与裁定

- **顺带修掉的旧毛病**：原 `prompt()` 文案里 `\n` 写错，弹窗会显示字面量「\n」；新实现不再有该问题。
- **提示位置**：从 `showToast`（页面角落）移到输入框右侧，`is-error` 时用低饱和红，与可选池提示同色系。
- **候选来源**：`options.skill_base` 的 39 个官方技能名；`类别:专攻` 仍需手打，由 `normalizeSkillName` 规范化。
