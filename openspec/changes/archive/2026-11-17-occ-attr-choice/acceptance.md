# 职业点本职属性选择 — 验收记录

实施分支：`master`；版本 2.1.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 公式候选项 | `test_trpg_coc_occ_attr.py::TestFormulaOptions` | 通过 |
| AC02 默认取高 | `test_default_takes_higher`：猎人（EDU80 STR45 DEX70）→ 300 | 通过 |
| AC03 按选择算 | `test_chosen_lower_attribute`：按力量 → 250；`test_chosen_higher_attribute`：按敏捷 → 300 | 通过 |
| AC04 自定义职业 | `test_custom_occupation_blank_is_edu4`（320）、`test_custom_occupation_second_attribute`（290） | 通过 |
| AC05 校验 | `TestAttrProblems` 7 例（非法候选项 / 无「或」职业填属性 / 无职业填属性 / 自定义职业八属性 / `validate` 拦截） | 通过 |
| AC06 数据修正 | `TestOccupationData`：两条海员公式与预算 300；猎人/私家侦探措辞 | 通过 |
| AC07 落库与回传 | `check_trpg_coc_api.py`：按力量 210、按敏捷 200、非法 400、自定义留空 180 / 意志 220、无「或」400（脚本共 85 项全过） | 通过 |
| AC08 页面选择器 | `node test/test_trpg_coc_occ_attr.js`：20 项（3/9/0 个选项、留空说明、非法值清空、选中后 250、CSS 定义） | 通过 |
| AC09 全量回归 | `python -m pytest -q` → **998 passed**（5:35） | 通过 |
| AC10 文档与归档 | `openspec validate coc-character-sheet --strict` valid；`CHANGELOG [2.1.0]` 与 `BOTERO_VERSION = "2.1.0"` 一致；同一 commit 归档 | 通过 |

## 数据修正明细

| 职业 | 修前 | 修后 | 性质 |
|---|---|---|---|
| 海员-军舰海员 | 教育×4 | 教育×2＋敏捷或力量×2 | **数值修正**（教育 80 时 320→300） |
| 海员-民船海员 | 教育×4 | 教育×2＋敏捷或力量×2 | **数值修正** |
| 22 个职业 | `教育×2＋敏捷或力量×2` / 半角 `+` | `教育×2＋力量或敏捷×2` | 措辞统一，数值不变 |

## 已知差异（未处理）

新卡 `职业列表` 里有 6 个职业名重复（艺术家、工匠、艺人、律师、私家侦探、科学家）。后一组（行 208–226）用新版技能译名（艺术及手艺、其他语言、母版名称），与我们的技能体系（技艺、外语）不一致；本次统一按**首个同名行**对齐，后一组不引入。若将来迁移技能译名，这 6 个职业需要连同本职技能一起重做。
