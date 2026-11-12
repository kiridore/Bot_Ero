# 实施与验收任务

- [x] 1.1 `core/trpg/coc.py`：`DYNAMIC_BASES` / `dynamic_skill_base` / `skill_base_for`，finalize 与 skill_defaults 接入，附表键规范化。对应 AC01–AC05。
- [x] 1.2 `core/trpg/growth.py`：补行改用 `skill_base_for(canon, card)`。对应 AC03。
- [x] 1.3 `webapp/trpg/app.py`：options 下发 `dynamic_bases`。对应 AC06。
- [x] 1.4 `webapp/static/trpg_coc.js`：`skillDefaults` / `skillBaseFor` 支持动态规则，重算时刷新闪避与母语。对应 AC06。
- [x] 1.5 测试：`TestDynamicBases`（6 例）、node 用例扩展、API 断言；修正 1 处技能计数断言。对应 AC01–AC06。
- [x] 1.6 `CHANGELOG [1.80.4]`、`BOTERO_VERSION`、归档与实现同一 commit。对应 AC07。
