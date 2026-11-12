# 实施与验收任务

- [x] 1.1 新建 `core/trpg/asset_data.py`：6 币种 × 6 档 × 三项 + 五类分类。对应 AC02。
- [x] 1.2 `core/trpg/coc.py`：`level_for_credit` / `asset_reference` / `asset_problems`，接入 `validate()` 与 `format_sheet()`。对应 AC01–AC03。
- [x] 1.3 `webapp/trpg/app.py`：options 下发币种/档位/分类，新增 asset-reference 接口。对应 AC04。
- [x] 1.4 `webapp/static/trpg_coc.js`：生活水平与币种下拉、其他资产、五类明细、总和、按规则填入、档位提示。对应 AC01、AC05。
- [x] 1.5 `webapp/static/char_view.js`：查看页展示新字段与总和。对应 AC06。
- [x] 1.6 测试：`TestAssets`（9 例）、`test_trpg_coc_assets.js`（7 项）、API 断言、查看页 DOM 断言。对应 AC01–AC06。
- [x] 1.7 `CHANGELOG [1.80.0]`、`BOTERO_VERSION`、归档与实现同一 commit。对应 AC07。
