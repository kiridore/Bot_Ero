# 实施与验收任务

- [x] 1.1 新增 `core/trpg/occupation_skills.json`：113 个职业的结构化本职技能（并行整理）。对应 AC01。
- [x] 1.2 `core/trpg/coc_data.py` 载入 JSON；`coc.py` 实现 `occupational_point_problems()` 并接入 `validate()`。对应 AC02。
- [x] 1.3 `test/test_trpg_coc_occupations.py`：数据完整性与归属校验用例。对应 AC01、AC02。
- [x] 1.4 `check_trpg_coc_api.py`：越界职业点 400。对应 AC03。
- [x] 1.5 建卡页展示可选池标注、下拉过滤工具残留。对应 AC04。
- [x] 1.6 `CHANGELOG [1.72.0]`、`BOTERO_VERSION`、归档与实现同一 commit。对应 AC05。
