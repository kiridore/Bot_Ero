# 实施与验收任务

- [x] 1.1 `core/trpg/coc.py`：`skill_base_map()` / `default_skill_names()`，`finalize` 与 `skill_defaults` 改用统一表。对应 AC01、AC02、AC05。
- [x] 1.2 `core/trpg/growth.py`：补行基础值改用 `skill_base_map()`。对应 AC02。
- [x] 1.3 `webapp/trpg/app.py`：options 下发统一表与播种名单。对应 AC03。
- [x] 1.4 `webapp/static/trpg_coc.js`：`skillBaseFor()` 统一查值，播种按名单，四处补行改用它。对应 AC03、AC04。
- [x] 1.5 测试：`TestSkillBaseConsistency`（5 例）、node 用例调整、API 2 条断言。对应 AC01–AC05。
- [x] 1.6 `CHANGELOG [1.80.3]`、`BOTERO_VERSION`、归档与实现同一 commit。对应 AC06。
