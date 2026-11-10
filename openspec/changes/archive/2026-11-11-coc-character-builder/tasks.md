# 实施与验收任务

> 提案 `proposal.md`；规范：新增 `coc-character-sheet`，修改 `trpg-party-setup`。

## 1. 数据层

- [x] 1.1 从 `docs/COC七版人物卡v1.6.1.xlsx` 提取技能基础值、技能类别与 114 个职业模板到 `core/trpg/coc_data.py`。对应 AC01、AC04。
- [x] 1.2 新建 `core/trpg/coc.py`：`finalize`（HP/MP/SAN/MOV/DB/体格/闪避、技能合计、职业与兴趣预算）、`validate`（职业、预算、信用区间、数值范围）、`skill_value`（精确/前缀/别名）、`format_sheet`（调查员简表）。对应 AC01–AC03。

## 2. 接口与插件

- [x] 2.1 `webapp/trpg/app.py`：`CharacterIn` 增 `rules` 与 COC 字段（职业/年龄/性别/居所/故乡/时代/幸运/信用评级/克苏鲁神话/技能/武器/资产/背景）；`_apply_rules` 按规则分派 finalize 与校验；`CharOut` 兼容两套卡；新增 `GET /api/trpg/coc/options`；新增 `/trpg/coc` 与 `/trpg/coc/{char_id}` 页面路由。对应 AC04。
- [x] 2.2 `plugins/trpg_char`：`/跑团 角色 查看` 与列表按卡片规则输出（COC 用调查员简表）。对应 AC03。
- [x] 2.3 `plugins/trpg_dice`：`.ra <技能名>` 从当前 COC 卡取成功率，未知技能给出提示；数值写法不变。对应 AC06。
- [x] 2.4 `plugins/trpg_session`：`/跑团 准备` 增加卡片规则与本团规则一致性校验。对应 AC05。

## 3. 前端

- [x] 3.1 新建 `webapp/static/trpg_coc.html` + `trpg_coc.js`：信息/属性（掷骰）/职业（自动填信用下限与预算提示）/技能表（实时合计与预算告警）/资产/背景/笔记，保存与编辑。对应 AC04、AC08。
- [x] 3.2 `webapp/static/trpg.js`：列表拆成「新建 DND 5E 卡」「新建 COC 7th 卡」，COC 卡显示调查员摘要且编辑跳转建卡页；`trpg.css` 增建卡工具样式。对应 AC08。

## 4. 测试

- [x] 4.1 新建 `test/test_trpg_coc.py`：派生值边界、价格表、预算公式、校验分支、技能查询与简表。对应 AC01–AC03。
- [x] 4.2 新建 `test/scripts/check_trpg_coc_api.py`：选项接口、建卡/更新派生值、三类 400、规则字段保留。对应 AC04。
- [x] 4.3 `test/test_trpg_session.py` 增规则不一致准备用例；`test/test_trpg.py` 增 `.ra 技能名` 与未知技能用例。对应 AC05、AC06。

## 5. 文档与交付

- [x] 5.1 `kb/PLUGIN_CATALOG.md`、`specs/plugin-catalog.md` 更新角色卡描述（两套规则、COC 建卡页）。对应 AC07。
- [x] 5.2 `CHANGELOG.md` 新增 `[1.66.0]`，`core/config.py::BOTERO_VERSION` bump 至 1.66.0。对应 AC07。
- [x] 5.3 全量 `pytest` 绿；`openspec validate` 两个能力 `--strict` 通过；逐条 AC 写 `acceptance.md`；归档与实现同一 commit。AC08 由所有者在部署机执行后补记。
