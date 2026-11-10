# 实施与验收任务

> 提案 `proposal.md`；设计 `design.md`；规范：新增 `trpg-rule-selection`、`trpg-dice-coc`，修改 `trpg-session-recording`、`trpg-record-web`。

## 1. 规则基础设施

- [x] 1.1 新建 `core/trpg/game_systems.py`：`DEFAULT_RULE`、`GAME_SYSTEMS`（dnd5e / coc7th，含展示名、检定指令、处理器、别名）、`rule_name()`、`normalize_rule()`；`plugins/trpg_dice/games.py` 改为重导出。对应 AC01。
- [x] 1.2 `core/trpg/party.py`：`default_pending` 增 `rules`；`read_pending` 缺字段补默认；新增 `set_rule()` 与 `current_rule()`（录制中取会话规则，否则取 pending，再否则默认）。对应 AC02、AC03。

## 2. COC 恢复

- [x] 2.1 新建 `plugins/trpg_dice/rolls.py`：`coc_check`（成功等级）、`coc_bonus`、`coc_penalty`（从 git 历史恢复）。对应 AC04、AC05。
- [x] 2.2 `plugins/trpg_dice/__init__.py`：`.ra` 路由与 `_handle_coc_check`；`.r c<值>`、`.rh c<值>`；奖惩骰 `.r b<n>` / `.r p<n>` 与 `.r 1d100b<n>` / `p<n>` 后缀；规则门控（DND 下拒绝 COC 指令、COC 下拒绝 `.rc`）。对应 AC04–AC06。

## 3. 会话与记录

- [x] 3.1 `plugins/trpg_session/__init__.py`：`PARTY_SUBCMDS` 增 `规则`；`_handle_rule`（无参列规则、DM 切换、录制中拒绝、未知规则拒绝）；开录写 `meta.rules` 与会话 `rules`；`resume_session` 从 `meta.rules` 恢复。对应 AC02、AC03。

## 4. 网页

- [x] 4.1 `webapp/trpg/app.py`：列表新增 `rules`/`rules_name`/`player_count`/`my_role`；详情新增 `rules`/`rules_name`；新增 `_my_role` 辅助函数。对应 AC07。
- [x] 4.2 `webapp/static/trpg_records.js` 改行式条目（团名+状态/起止时间/人数/我的身份/规则/条数），`trpg_record.js` 头部加规则，`trpg.css` 的卡片样式改为行式并删除导出徽标样式。对应 AC07、AC08。

## 5. 测试

- [x] 5.1 `test/test_trpg.py`：规则注册表变体、COC 成功等级边界、`.ra`/`.r c`、奖惩骰两种写法与数量越界、DND/COC 双向门控（原 `.ra` 不匹配的两个旧用例改为匹配并被门控拒绝）。对应 AC01、AC04–AC06。
- [x] 5.2 `test/test_trpg_session.py`：`/跑团 规则` 查看/切换/权限/录制中拒绝/未知规则、开录写 `meta.rules`、续录恢复规则。对应 AC02、AC03。
- [x] 5.3 `test/scripts/check_trpg_records_api.py`：meta 辅助函数支持 `rules`，断言 `rules_name`、`player_count`、`my_role`。对应 AC07。
- [x] 5.4 新建 `test/test_trpg_records_list_dom.js`：行式条目字段与 `mine=1` 查询；`test/test_trpg_records_dom.js` 跑通详情页。对应 AC07、AC08。

## 6. 文档与交付

- [x] 6.1 `plugins/menu/bot_menu_text.py` 增 `/跑团 规则`、`.ra`、奖惩骰行并标注规则前提；`kb/QUICK_REFERENCE.md`、`kb/PLUGIN_CATALOG.md`、`specs/plugin-catalog.md` 同步。对应 AC09。
- [x] 6.2 `CHANGELOG.md` 新增 `[1.65.0]`，`core/config.py::BOTERO_VERSION` bump 至 1.65.0。对应 AC09。
- [x] 6.3 全量 `pytest` 绿；四个能力 `openspec validate --strict` 通过；逐条 AC 写 `acceptance.md`；`openspec archive 2026-11-11-trpg-rule-switch-and-record-list` 与实现同一 commit。AC10 由所有者在部署机执行后补记。
