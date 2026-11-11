# 实施与验收任务

## 1. 领域逻辑

- [x] 1.1 新建 `core/trpg/levelup.py`：`status`、`can_level_up`、`next_threshold`、`asi_required`、`hp_gain`、`validate_asi`、`apply_level_up`。对应 AC01–AC04。
- [x] 1.2 `core/trpg/character.py`：`finalize` 等级改用卡片 `level`（仅缺失时按 XP 兜底）；`format_sheet` 增加可升级/进度行。对应 AC06、AC07。

## 2. 接口与页面

- [x] 2.1 `webapp/trpg/app.py`：`POST /api/me/characters/{id}/levelup`、`GET /trpg/levelup/{id}`、`CharOut` 增加 `can_level_up`/`xp_to_next`/`hp_gain`。对应 AC05。
- [x] 2.2 新建 `webapp/static/trpg_levelup.html` 与 `trpg_levelup.js`：三步向导、ASI 实时上限提示、成功后展示增长。对应 AC05、AC08。
- [x] 2.3 `webapp/static/trpg.js`：列表升级入口、编辑页等级显示改为「进度 / 已够升级」。对应 AC06。

## 3. 测试

- [x] 3.1 新建 `test/test_trpg_levelup.py`（25 例）：可升级判定、HP 增长、ASI 规则、升级落盘。对应 AC01–AC04。
- [x] 3.2 新建 `test/scripts/check_trpg_levelup_api.py`：建卡标记、均值升级、XP 不足、ASI 缺失与分配、超上限、满级、COC 拒绝。对应 AC05。
- [x] 3.3 `test/test_trpg_finalize.py`：等级不再由 XP 推导。对应 AC06。

## 4. 文档与交付

- [x] 4.1 `CHANGELOG [1.71.0]`、`BOTERO_VERSION`、`kb/QUICK_REFERENCE.md` 同步。对应 AC07。
- [x] 4.2 全量 `pytest` 绿；`openspec validate dnd-level-up --strict` 通过；写 `acceptance.md`；归档与实现同一 commit。AC08 由所有者验收。
