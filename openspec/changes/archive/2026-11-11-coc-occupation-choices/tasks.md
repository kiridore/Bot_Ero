# 实施与验收任务

- [x] 1.1 `core/trpg/coc.py`：`occupation_structure`、`occupation_choice_problems`、`occupation_choice_warnings`，`occupational_point_problems` 改为只认固定项 + 已选项。对应 AC01–AC03。
- [x] 1.2 `webapp/trpg/app.py`：`CharacterIn`/`CharOut` 增加 `occupation_choices`。对应 AC04。
- [x] 1.3 `webapp/static/trpg_coc.js`：按池渲染控件（多选/输入）、切换职业重置、自动补技能行、未选满提示、收集与回填。对应 AC05。
- [x] 1.4 `test/test_trpg_coc_occupations.py`：补充选择校验、归属校验、未选满提示用例；修正旧夹具。对应 AC01–AC03。
- [x] 1.5 `check_trpg_coc_api.py`：选择回传、未选入池加点、池外选择、超选四类断言。对应 AC04。
- [x] 1.6 `CHANGELOG [1.73.0]`、`BOTERO_VERSION`、归档与实现同一 commit。对应 AC06。
