# 可选池显式选择 — 验收记录

实施分支：`master`；版本 1.73.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 选择校验 | `test_trpg_coc_occupations.py`：池外选择（「攀爬」不在摄影师社交池）报「不在可选池」；表外技能名报「不在技能表内」；未知池下标报「没有第 9 个可选池」；超配额报「最多选 N 项」 | 通过 |
| AC02 归属校验 | 固定项直接加点通过；未选定即给池内技能加点被拒；选定后通过；`类别:*` 池选定 `格斗:斗殴` 通过、`技艺:摄影` 报错 | 通过 |
| AC03 未选满提示 | `occupation_choice_warnings` 返回「摄影师的可选池 #1 还差 1 项」；选满后为空；`validate()` 不因此报错 | 通过 |
| AC04 接口 | `check_trpg_coc_api.py` 全过：`occupation_choices` 随建卡回传；未选入池即加点 400；池外选择 400；超选 400 | 通过 |
| AC05 页面 | 具名池渲染多选框、`类别:*`/`*` 池渲染文本框；`syncChosenSkills()` 自动补技能行；职业切换重置选择；未选满提示行 | 代码层通过，浏览器手测待确认 |
| AC06 文档与归档 | 全量 `pytest` → **719 passed**（4:38）；`openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.73.0]` 与 `BOTERO_VERSION = "1.73.0"` 一致 | 通过 |

## 实测与裁定

- **语义变化**：池从「上限」变成「选择」。`occupational_point_problems()` 不再按池配额贪心分配，而是只认 `required` ∪ `occupation_choices`；配额与池外校验移到 `occupation_choice_problems()`。
- **未选满不拦**：`validate()` 不含 warning，页面单独显示「还差 N 项」，避免建卡中途存不了草稿。
- **测试夹具修正**：原有 `test_trpg_coc.py` 的药剂师卡把职业点加在「科学:化学」却没记录选择，已补 `occupation_choices: {"1": ["科学:化学"]}`。
- **未做**：不兼容旧卡（所有者确认无生产旧卡）；`occupation_choices` 不参与 `.ra`/角色卡查看的输出。
