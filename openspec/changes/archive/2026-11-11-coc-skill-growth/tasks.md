# 实施与验收任务

## 1. 规则与计算

- [x] 1.1 `plugins/trpg_dice/rolls.py`：大失败口径（≥50 仅 100、<50 为 96-100）、01 大成功、技能值上限 199。对应 AC01。
- [x] 1.2 `core/trpg/coc.py`：`SKILL_CEILING=199`，`skill_total` 与保存校验放宽，技能可超 100。对应 AC07。
- [x] 1.3 新建 `core/trpg/growth.py`：`improves`、`mark`（含别名解析）、`checked_skills`、`settle`（含 90%+ SAN 奖励与清空标记）。对应 AC02、AC04、AC05。

## 2. 指令

- [x] 2.1 `plugins/trpg_dice/__init__.py`：`.ra <技能名>` 成功时打勾并写卡、回执提示。对应 AC03。
- [x] 2.2 `plugins/trpg_session/__init__.py`：`/跑团 成长 [@人]` 结算、权限、规则门控。对应 AC04–AC06。
- [x] 2.3 `webapp/static/trpg_coc.js`：成长列上限 199、只读显示勾标记。对应 AC07。

## 3. 测试

- [x] 3.1 新建 `test/test_trpg_growth.py`（18 例）：检定口径、成长判定、标记与别名、结算与清空、90%+ 奖励与上限。对应 AC01–AC05。
- [x] 3.2 `test/test_trpg.py`：更新大失败断言、新增打勾与失败不打勾用例。对应 AC03。
- [x] 3.3 `test/test_trpg_session.py`：新增 `TestGrowth` 5 例（结算、无标记、DND 卡、规则不符、非 DM @）。对应 AC06。
- [x] 3.4 `test/scripts/check_trpg_coc_api.py`：成长超 100% 可保存。对应 AC07。

## 4. 文档与交付

- [x] 4.1 菜单、`kb/QUICK_REFERENCE.md`、`CHANGELOG [1.70.0]`、`BOTERO_VERSION` 同步。对应 AC08。
- [x] 4.2 全量 `pytest` 绿；`openspec validate coc-skill-growth --strict` 通过；写 `acceptance.md`；归档与实现同一 commit。AC09 由所有者验收。
