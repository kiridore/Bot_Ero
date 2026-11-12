# 实施与验收任务

- [x] 1.1 `core/trpg/coc.py`：`skill_defaults()`、finalize 补默认技能、闪避按 `DEX//2`。对应 AC01–AC03。
- [x] 1.2 `core/trpg/coc.py::validate`：允许无职业；无职业时拒绝职业点。对应 AC04。
- [x] 1.3 `webapp/static/trpg_coc.js`：`skillDefaults`/`mergeSkillDefaults`、加载时合并、闪避基础值随敏捷刷新。对应 AC05。
- [x] 1.4 测试：`TestSkillDefaults`（5 例）、`test_trpg_coc_skill_defaults.js`（9 项）、API 三项断言；修正 3 处受影响的旧用例。对应 AC01–AC06。
- [x] 1.5 `CHANGELOG [1.79.0]`、`BOTERO_VERSION`、归档与实现同一 commit。对应 AC07。
