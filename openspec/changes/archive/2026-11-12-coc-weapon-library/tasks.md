# 实施与验收任务

- [x] 1.1 从 `docs/COC7空白卡CY26.3.xlsx`「武器列表 战斗」生成 `core/trpg/weapon_data.py`（104 条，含 rare/outdated 标记）。对应 AC01。
- [x] 1.2 `core/trpg/coc.py`：`weapon_skill_ok`、`damage_with_db`、伤害校验放宽、次数写法扩展、类型与使用技能校验。对应 AC02、AC03、AC06。
- [x] 1.3 `webapp/trpg/app.py`：options 下发 `weapon_library`。对应 AC05。
- [x] 1.4 `webapp/static/trpg_coc.js`：类型/使用技能列、武器库下拉与时代筛选、实际伤害列 DB 标注、`/跑团 角色 查看` 输出武器行。对应 AC04–AC06。
- [x] 1.5 `core/trpg/coc.py::format_sheet`：追加武器段落含 DB 标注。对应 AC06。
- [x] 1.6 测试：`test_trpg_coc.py` 5 例新增、`test_trpg_coc_weapon_era.js`、`check_trpg_coc_api.py` 4 项断言、`check_trpg_coc_api.py` 夹具补字段。对应 AC01–AC06。
- [x] 1.7 `CHANGELOG [1.77.0]`、`BOTERO_VERSION`、归档与实现同一 commit。对应 AC07。
