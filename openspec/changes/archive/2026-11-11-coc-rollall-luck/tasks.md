# 实施与验收任务

- [x] 1.1 `webapp/static/trpg_coc.js`：`rollAll` 补幸运 `3d6` 重掷。对应 AC01、AC02。
- [x] 1.2 删除 `rollDieReady()` 死别名，幸运掷骰统一走 `rollDie`。对应 AC01。
- [x] 1.3 `test/test_trpg_coc.py` 新增 `TestBuilderScript`（2 例）：`rollAll` 覆盖幸运、脚本中无 `rollDieReady`。对应 AC01。
- [x] 1.4 `CHANGELOG [1.71.2]` 与 `BOTERO_VERSION`；全量 `pytest` 绿；归档与实现同一 commit。对应 AC03。
