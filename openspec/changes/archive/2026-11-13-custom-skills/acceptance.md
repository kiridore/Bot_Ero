# 技能名自由填写 — 验收记录

实施分支：`master`；版本 1.96.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 无下拉 | `TestBuilderScript::test_add_skill_uses_inline_input`：含 `id="skillName"`，不含 `list="skillOptions"` 与 `<datalist` | 通过 |
| AC02 归一化放行 | `node test/test_trpg_coc_skill_name.js` 20 项：「飞天」→「飞天」、去首尾空白保留内部空格、空串→`""`、官方名与 `类别:专攻` 照旧 | 通过 |
| AC03 服务端保留 | `test_custom_skill_persists`：`finalize` 保留 35%、`skill_value` 35、`is_known_skill` 为假 | 通过 |
| AC04 成长 | `test_trpg_growth.py::test_custom_skill_marked`：自定义技能打勾成功且基础值 0 | 通过 |
| AC05 可选池仍严 | `test_occupation_pool_still_strict` / `test_choice_unknown_skill_rejected`：仍报「不在技能表内」 | 通过 |
| AC06 接口 | `check_trpg_coc_api.py`：自定义技能 200 且保留 35%；超长技能名 400 并提示「技能名…不合法」 | 通过 |
| AC07 全量回归 | `python -m pytest -q` → **944 passed**（5:11） | 通过 |
| AC08 文档与归档 | `openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.96.0]` 与 `BOTERO_VERSION = "1.96.0"` 一致；同一 commit 归档 | 通过 |

## 行为对照

| 输入 | 以前 | 现在 |
|---|---|---|
| `侦察` | 自动填 25 | 自动填 25 |
| `射击:手枪` | 自动填 20（1.95.0 起） | 自动填 20 |
| `飞天` | 拒绝添加；绕过页面写入会被 finalize 丢弃 | 接受，基础值 0 可编辑，保存后可用 |
| `很…(31 字)` | 无限制 | 拒绝（输入框提示 / 保存 400） |
| 职业可选池填 `飞天` | 拒绝 | 仍然拒绝 |

## 说明

- `skill_name_ok()` 的放宽只针对「名字本身」；合法性仅限长度与换行。空名、超长名在保存时报错，不再静默丢弃。
- 自定义技能不进 `occupation_skills.json` 的匹配，所以不能加职业点（会提示不是本职技能），但兴趣点与成长照常。
- 名称归一化保留内部空格（如「黑客 工具」），只去首尾空白。
- `skill_base_map()` 仍是基础值的唯一来源：认识的技能即使手改基础值，`finalize` 也会按规则表覆盖（与之前一致）；自定义技能则沿用卡上的值。
