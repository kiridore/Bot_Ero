# 实施与验收任务

- [x] 1.1 `core/trpg/coc.py`：`weapon_skill_base()`、`skill_value()` 回落、`skill_name_ok()` 放宽。对应 AC01、AC02。
- [x] 1.2 `core/trpg/growth.py`：`mark()` 缺行时按附表/武器技能表补行。对应 AC03、AC04。
- [x] 1.3 新建 `core/web/static/trpg_assets.js`，建卡页与查看页改用共享实现。对应 AC05。
- [x] 1.4 测试：`TestWeaponSkills`（4 例）、`TestGrowthMarkDefaults`（4 例）、资产 node 用例迁移、查看页 DOM 用例加载共享文件。对应 AC01–AC05。
- [x] 1.5 `CHANGELOG [1.80.2]`、`BOTERO_VERSION`、归档与实现同一 commit。对应 AC06。
