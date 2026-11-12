# 实施与验收任务

- [x] 1.1 `core/trpg/coc.py`：`AGE_BANDS` / `age_adjustment()` / `age_mov_penalty` 改公式 / `apply_age_adjust()` / `undo_age_adjust()`。对应 AC01、AC02。
- [x] 1.2 `validate()` 增加年龄与 `age_adjust` 校验。对应 AC04。
- [x] 1.3 `webapp/trpg/app.py`：`CharacterIn` 增 `age_adjust`；`PUT` 保留原值；`POST/DELETE .../age-adjust`。对应 AC03、AC05。
- [x] 1.4 `webapp/static/trpg_coc.js` + `trpg.css`：年龄调整区块、体能输入、只读锁定、幸运取高。对应 AC07。
- [x] 1.5 `webapp/static/char_view.js`：查看页显示年龄调整摘要（一行）。
- [x] 1.6 测试：`test/test_trpg_coc_age.py`、`test/scripts/check_trpg_coc_api.py` 增断言、`test/test_trpg_coc_age_dom.js`。对应 AC01–AC07。
- [x] 1.7 文档：`kb/GAMEPLAY.md` 年龄调整表、`CHANGELOG [1.83.0]`、`BOTERO_VERSION`。对应 AC09。
- [x] 1.8 逐条填写 `acceptance.md` → `openspec validate --strict` → `openspec archive`（与实现同一 commit）。对应 AC08、AC09。
