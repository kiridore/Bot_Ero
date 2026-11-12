# 实施与验收任务

- [x] 1.1 `core/trpg/coc.py`：`INVENTORY_STATUSES`、`inventory_problems`、`inventory_summary`，接入 `validate()` 与 `format_sheet()`。对应 AC01、AC02。
- [x] 1.2 `webapp/trpg/app.py`：模型字段 + options 下发状态。对应 AC03。
- [x] 1.3 `webapp/static/trpg_coc.js`：物品表格、添加/删除、实时合计、收集。对应 AC04。
- [x] 1.4 `webapp/static/char_view.js`：按状态分组展示与合计。对应 AC04。
- [x] 1.5 `core/trpg/snapshots.py`：`inventory_count` / `inventory_slots`。对应 AC05。
- [x] 1.6 测试：`TestInventory`（8 例）、`TestInventorySnapshot`（2 例）、API 3 条、查看页 1 条。对应 AC01–AC05。
- [x] 1.7 `CHANGELOG [1.81.0]`、`BOTERO_VERSION`、归档与实现同一 commit。对应 AC06。
