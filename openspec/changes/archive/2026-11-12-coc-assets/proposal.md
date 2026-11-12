# COC 资产栏对齐新卡：6 档生活水平、币种与参考值

## Why

新卡（`docs/COC7空白卡CY26.3.xlsx`）的资产区有信用评级、生活水平（6 档）、消费水平、其他资产、当前现金、币种六项，下面还有「其他资产表」（交通工具/住所/奢侈品/股票证券/其他）与资产总和。我们目前只有三个自由文本框（现金/消费水平/生活水平）加一个信用评级数字框，生活水平可以填任意文字，也没有任何按规则推导的数值。

配套的「资产及物价参考」工作表给出 6 种货币/时代 × 6 档生活水平的对照：现金与其他资产按信用评级乘算。这些数据在卡片上是现成的，只是没人用。

## What Changes

- 新增 `core/trpg/asset_data.py`：6 个币种（日元/人民币/美元现代/美元1920s/英镑维多利亚/澳元）× 6 档生活水平 × 三项（现金/其他资产/消费水平），三种取值写法（固定值 / CR×N / 文本），另有其他资产表五个分类。
- `core/trpg/coc.py`：`level_for_credit()`、`asset_reference()`、`asset_problems()`；`validate()` 接入资产校验；`format_sheet()` 增加资产摘要行。
- `webapp/trpg/app.py`：options 下发币种/档位/分类；新增 `GET /api/trpg/coc/asset-reference?currency=&credit=&level=`。
- 建卡页：生活水平改下拉、币种下拉、其他资产文本框、其他资产表五项 + 资产总和（自动）/剩余资产值；「按规则填入」按钮按 CR 查表填现金/消费水平/档位；信用评级变化时档位跟随（可手改）；顶部提示当前 CR 通常对应哪一档。
- 查看页：资产区块展示币种、各项明细与资产总和。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：资产栏字段、参考值与校验。

## Scope and Compatibility

- 生活水平由自由文本改为 6 档枚举；旧卡若填了别的词，保存时会提示「不在 6 档之内」（当前环境无生产旧卡）。
- 币种为 6 项枚举，空值允许；参考值只做「填入建议」，不强制覆盖玩家手填的金额。
- 资产总和由现金 + 五类明细相加得出，只读；剩余资产值可手填。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 档位映射 | `python -m pytest test/test_trpg_coc.py -q -k Assets` | 0→身无分文、1–9→拮据、10–49→标准、50–89→小康、90–98→富裕、99→富豪，边界值逐一断言 |
| AC02 参考值 | 同上 | 日元 CR30 → 现金 120000 / 其他资产 4500000 / 消费水平 25000；CR99 取固定值 3000万；英镑 CR10 现金 100、消费水平文本「2镑10先令」；未知币种返回 None |
| AC03 校验 | 同上 + `check_trpg_coc_api.py` | 未知币种、非法生活水平、非数字/负数分类值均被拒 |
| AC04 接口 | `python test/scripts/check_trpg_coc_api.py` | asset-reference 返回参考值、未知币种 400；带新字段的卡可保存并原样回传；options 下发 6 币种 / 6 档位 / 5 分类 |
| AC05 合计 | `node test/test_trpg_coc_assets.js` | 合计 = 现金 + 五类；带货币符号/非数字/空值时不崩溃 |
| AC06 查看页 | `node test/test_trpg_coc_view_dom.js` | 展示币种、其他资产、剩余资产值与资产总和 |
| AC07 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿；`CHANGELOG [1.80.0]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
