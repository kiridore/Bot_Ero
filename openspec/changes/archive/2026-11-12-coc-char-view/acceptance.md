# COC 角色卡查看页 — 验收记录

实施分支：`master`；版本 1.77.2。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 COC 分支 | `test_trpg_coc_view_dom.js`：COC 卡渲染出「田宫真莉 / 药剂师 / 28岁 / 1920s / 东京」，DND 卡走原分支（含 `Lv.1`、无「调查员笔记」） | 通过 |
| AC02 派生数值 | 同一用例断言 `HP 8/10`、`SAN 40/99`、`MOV 9`、`+1D4`、`闪避 27`、`信用评级 40` 全部出现 | 通过 |
| AC03 九项属性 | 九项名称全部渲染 | 通过 |
| AC04 技能与武器 | 技能 `科学:制药 21% ✓`；武器含类型/使用技能/装弹量/贯穿；伤害渲染为 `2D6+DB（DB=+1D4）` | 通过 |
| AC05 背景与笔记 | 资产（现金 40 等）、背景（冷静）、笔记均渲染 | 通过 |
| AC06 接口契约 | `check_trpg_coc_api.py`：公共卡片接口返回 `rules=coc7th`、`scores.力量=60`、含 `skills`/`weapons`，武器带 `type`/`skill` | 通过 |
| AC07 文档与归档 | 全量 `pytest` → **763 passed**（4:44）；`openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.77.2]` 与 `BOTERO_VERSION = "1.77.2"` 一致 | 通过 |

## 实测与裁定

- **根因**：查看页从未跟进 1.66 起的 COC 支持，只读 DND 字段（`rules.attributes` / `rules.skills` / `level` / `ac` / `proficient_skills`）。接口本身是完整的（`_char_to_out` 对 COC 会算 `finalize()`），所以问题纯粹在渲染层。
- **不复制计算**：查看页不重算派生值，直接用接口下发的 `hp/mp/san/max_san/mov/db/build/dodge/skills`，避免与建卡页两套口径。
- **DB 标注**：`damageWithDb` 只在伤害含 `DB` 时追加 `（DB=…）`，与建卡页「实际伤害」列规则一致。
- **未做**：查看页不显示「您的角色可能（只是可能！）」文案；公共卡页仍是只读，不提供编辑入口。
