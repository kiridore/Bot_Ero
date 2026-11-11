# 实施与验收任务

- [x] 1.1 `webapp/static/trpg_coc.js`：新增 `canonSkill`/`normalizeSkillName`，`addSkill` 校验 + 去重提示。对应 AC01、AC02。
- [x] 1.2 `webapp/trpg/app.py`：`/api/trpg/coc/options` 增加 `skill_aliases`。对应 AC03。
- [x] 1.3 新建 `test/test_trpg_coc_skill_name.js`（9 例，截取源码函数执行）；`check_trpg_coc_api.py` 增加别名断言。对应 AC01、AC03。
- [x] 1.4 `CHANGELOG [1.71.4]` 与 `BOTERO_VERSION`；全量 `pytest` 绿；归档与实现同一 commit。对应 AC04。
