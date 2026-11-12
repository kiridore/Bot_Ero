# COC 资产栏 — 验收记录

实施分支：`master`；版本 1.80.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 档位映射 | `test_trpg_coc.py::TestAssets::test_level_for_credit`：0/1/9/10/49/50/89/90/98/99 十个边界逐一断言 | 通过 |
| AC02 参考值 | `test_reference_jpy`（CR30 → 120000/4500000/25000）、`test_reference_flat_bracket`（CR99 → 3000万/300亿）、`test_reference_text_bracket`（英镑 100 / 「2镑10先令」）、`test_reference_unknown_currency`、`test_reference_explicit_level` | 通过 |
| AC03 校验 | `test_asset_problems` + `test_validate_includes_assets`：未知币种、非法档位、非数字、负数均被拒 | 通过 |
| AC04 接口 | `check_trpg_coc_api.py`：asset-reference 正常与 400；带新字段的卡保存并原样回传；options 下发 6 币种 / 6 档位 / 5 分类 | 通过 |
| AC05 合计 | `test_trpg_coc_assets.js`：合计=现金+五类、带货币符号可算、非数字按 0、空值安全 | 通过 |
| AC06 查看页 | `test_trpg_coc_view_dom.js`：展示币种、其他资产、资产总和 420000 | 通过 |
| AC07 文档与归档 | 全量 `pytest` → **800 passed**（5:09）；`openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.80.0]` 与 `BOTERO_VERSION = "1.80.0"` 一致 | 通过 |

## 实测与裁定

- **数据来源**：`docs/COC7空白卡CY26.3.xlsx` 的「资产及物价参考」第 6–13 行与 15–22 行，按币种分块抄录；「富豪」档参考表给的是固定值（日元 3000万 / 其他资产 300亿），按固定值处理。
- **英镑的文本档位**：维多利亚时代用「5先令」「2镑10先令」，无法参与加法，因此参考值支持文本类型，前端原样填入、合计时按 0 处理。
- **档位与 CR 的关系**：默认跟随 CR（可手改），不一致时页面只提示不拦截——规则上绑死会挡住「继承遗产/破产」这类 KP 裁定。
- **合计口径**：资产总和 = 现金 + 五类明细；「其他资产」文本框是描述性的，不参与加法（与人物卡 61 行的语义一致）。
- **未做**：物价参考表（现代物价、货币汇率、疯狂表等）未接入，回答「这件装备多少钱」仍需查表。
