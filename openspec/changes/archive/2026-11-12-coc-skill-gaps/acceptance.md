# 成长标记 / 武器技能 / 资产合计 — 验收记录

实施分支：`master`；版本 1.80.2。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 武器技能基础值 | `TestWeaponSkills::test_weapon_skill_base_table`：斗殴 25、手枪 20、步枪/霰弹枪 25、弓 15、绞具 15，共 19 项 | 通过 |
| AC02 武器技能可用 | `test_skill_value_falls_back_to_weapon_base`：`.ra 斗殴`=25、`弓术`=15、`飞天`=None；`test_skill_name_ok_accepts_weapon_skill` | 通过 |
| AC03 成长标记补行 | `TestGrowthMarkDefaults`：会计补 base 5、科学:化学补 base 1、别名复用已有行（不新增）、飞天拒绝且不改卡 | 通过 |
| AC04 武器技能标记 | `TestWeaponSkills::test_weapon_skill_marks_growth`：mark 斗殴 → finalize total 25 | 通过 |
| AC05 共享资产合计 | `test_trpg_coc_assets.js`（8 项，含文本金额按 0）、`test_trpg_coc_view_dom.js` 资产总和 420000 | 通过 |
| AC06 文档与归档 | 全量 `pytest` → **813 passed**（5:09）；`openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.80.2]` 与 `BOTERO_VERSION = "1.80.2"` 一致 | 通过 |

## 实测与裁定

- **缺陷 1 复现方式**：`finalize` 有「会计」但 `growth.mark(card,"会计")` 返回 False（卡上无行）→ 成功检定打不上勾。
- **缺陷 2 复现方式**：`.ra 斗殴` 返回 None（武器技能不在 39 项标准技能里）。
- **武器技能基础值来源**：不从规则书手抄，而是从武器库用到的技能集合 + 附表 C 列基础值推导（`弓术→弓` 做别名），避免编造数字；`绞具` 附表给的是 15%（与常见记忆的 5% 不同，以表为准）。
- **不污染技能表**：武器技能不进 `finalize` 的默认补全，只在 `.ra` 查询与打勾补行时出现，避免每张卡多出 19 行。
- **`skill_name_ok` 放宽**：否则 `finalize` 会丢弃补出来的武器技能行（它用同一个函数过滤）。
- **资产合计**：抽到 `core/web/static/trpg_assets.js`，两页共用；文本金额（中文单位）按 0，带符号数字正常解析。
- **未做**：审计中列出的其他缺口（装备/背包、疯狂表、年龄修正、物价表、记录搜索与可见性等）不在本次范围。
