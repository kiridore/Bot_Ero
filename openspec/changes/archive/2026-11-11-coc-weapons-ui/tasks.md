# 实施与验收任务

- [x] 1.1 `webapp/static/trpg_coc.js`：新增武器区块（八列可增删行）、默认徒手格斗、`collect()` 收集并过滤空名称。对应 AC01、AC02。
- [x] 1.2 `test/scripts/check_trpg_coc_api.py`：建卡带两把武器并断言回传；更新为一把短棍并断言替换。对应 AC02。
- [x] 1.3 `CHANGELOG.md` 新增 `[1.68.0]`，`core/config.py::BOTERO_VERSION` bump 至 1.68.0。对应 AC03。
- [x] 1.4 全量 `pytest` 绿；`openspec validate coc-character-sheet --strict` 通过；写 `acceptance.md` 并归档；AC04 由所有者手工验收。
