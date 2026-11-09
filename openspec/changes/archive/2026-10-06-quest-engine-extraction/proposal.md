# 周常任务引擎迁出 core（社区版 T0.5）

> 纯重构：行为零变化，无 spec 级行为变更（skip_specs）。

## Why

`core/utils.py` 目前持有周常玩法规则（`QUEST_DEFS` 任务表 + `on_quest_trigger`/`on_quest_rollback` 发奖/撤奖逻辑 + `get_quest_week_key`）——core 反向承载了插件域的玩法规则，对应架构耦合点 C1（`docs/community/architecture-overview.md`）。社区版要求 core 只留纯工具（D5 接缝纪律），本任务把引擎整体迁入 `plugins/weekly_quest/engine.py`，为后续社区包按需裁剪玩法清障。

## What Changes

- **新建 `plugins/weekly_quest/engine.py`**：迁入 `QUEST_DEFS`（含 ponytail 注释）、`get_quest_week_key`、`on_quest_trigger`、`on_quest_rollback`；内部继续用 `core.utils.get_monday_to_monday`/`add_user_point`（绝对导入，plugins→core 合法方向）
- **`core/utils.py`**：删除上述四个定义（`get_monday_to_monday`、`add_user_point`、`register_plugin` 等纯工具保留原位）
- **改 import（5 个文件，已核对无基线漂移）**：`plugins/checkin/__init__.py:5`、`plugins/lottery/__init__.py:7`、`plugins/checkin_recall/__init__.py:6`、`plugins/roll_back/__init__.py:4`、`plugins/weekly_quest/__init__.py:3`——玩法符号改从 `plugins.weekly_quest.engine` 导入，core 符号留原 import
- **新增 `test/test_quest_engine.py`**：新家地址冒烟（trigger 达标发奖 / rollback 撤奖回退）

**不改**：函数体一字不动（纯搬家）；`core/db/quest.py` 数据层不动；weekly_report/webapp 不引用这些符号（已核实零引用）。

## Capabilities

- 无（纯重构，`.openspec.yaml` 已设 `skip_specs: true`）

## 验收标准

1. **core 出清**：`rg -n "QUEST_DEFS|on_quest_trigger|on_quest_rollback|get_quest_week_key" core/` 零命中；`core/utils.py` 仍含 `get_monday_to_monday` 与 `add_user_point`
2. **引用面完整迁移**：`rg -n "from core.utils import.*(on_quest|QUEST_DEFS|get_quest_week_key)" --type py` 零命中；5 个插件的玩法符号均从 `plugins.weekly_quest.engine` 导入且 `python -c "import plugins"` 成功（无循环导入）
3. **冒烟测试**：`python -m pytest test/test_quest_engine.py -v` 绿——seed 1 条本周打卡 → `on_quest_trigger(db, uid, "checkin")` 返回含「打个卡先 +1」且 `db.points.get(uid)` 增 1；删除该打卡 → `on_quest_rollback(db, uid, "checkin")` 后积分回退、撤奖生效
4. **等价回归**：全量 `pytest` 绿（现有周常/打卡/撤回/抽奖用例即行为等价证明，红线 #122 私有形态零变化）
