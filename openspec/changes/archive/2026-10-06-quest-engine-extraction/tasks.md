# Tasks · 周常任务引擎迁出 core（T0.5）

> 验收标准见 proposal.md（4 条）；纯重构记 CHANGELOG `[未发布]` 不 bump。

- [x] 1. 新建 `plugins/weekly_quest/engine.py`（四符号逐字迁入 + core.utils 依赖导入）
- [x] 2. 5 个插件 import 改造（checkin / lottery / checkin_recall / roll_back / weekly_quest）；`core/utils.py` 删除四定义
- [x] 3. 新增 `test/test_quest_engine.py`（trigger 发奖 / rollback 撤奖 / 新家符号断言）
- [x] 4. 验收 1-2：rg 出清核对 + `python -c "import plugins"` 无循环导入
- [x] 5. 全量 `pytest` 绿（验收 3-4）
- [x] 6. CHANGELOG `[未发布]`；development-plan 勾选 T0.5；`openspec archive quest-engine-extraction`，同 commit：`refactor(周常): 任务引擎从 core 迁入 weekly_quest 插件域`
