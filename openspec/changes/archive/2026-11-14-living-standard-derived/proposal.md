# 生活水平由信用评级推算，不再让玩家选

## Why

资产区的生活水平原本是个下拉框，默认跟着信用评级走、但允许玩家自己选一个不一致的档位，只在下方给一句提示。按规则书资产表（`docs/COC7空白卡CY26.3.xlsx` 的「资产及物价参考」），生活水平是由信用评级唯一决定的档位（0 身无分文 / 1–9 拮据 / 10–49 标准 / 50–89 小康 / 90–98 富裕 / 99 富豪），不该有第二个来源。

## What Changes

- 建卡页把 `<select id="living_standard">` 换成 `<output class="coc-readonly">`，值随信用评级实时变化；保存时提交的也是推算值。
- 「按规则填入」不再写生活水平（它不再可写），仍按币种 + 信用评级填现金与消费水平。
- `core/trpg/coc.py::normalize_credit_rating()` 保存时把 `assets.living_standard` 归一化为信用评级对应的档位；但如果原值是 6 档之外的字（脏数据），保持原样交给 `asset_problems()` 报 400，不静默吞掉。
- 测试：新增 `TestLivingStandardDerived` 4 例（跟随档位边界、信用 0、脏值仍报错、页面为 output）。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：生活水平的来源与呈现。

## Scope and Compatibility

- 旧卡里手选过的档位会在下次保存时被纠正为信用评级对应档位（符合规则表）。
- 档位与现金/其他资产/消费水平的参考值仍来自 `asset_data.LEVELS`，口径未变。
- 无数据库变更；版本 1.97.0（行为变化：少了一个可编辑项）。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 跟随信用评级 | `python -m pytest test/test_trpg_coc.py -q -k LivingStandard` | 信用 35/40 → 标准；50/60 → 小康；与卡上原值「富豪」无关 |
| AC02 信用 0 | 同上 | 无职业、无加点 → 身无分文 |
| AC03 脏值 | 同上 | `living_standard: "贫穷"` → 仍报「不在 6 档」400 且值不被改写 |
| AC04 页面 | 同上 | 源码含 `<output id="living_standard"`，不含 `<select id="living_standard"`；`collect` 提交 `levelForCredit(creditFromSkillRow())` |
| AC05 接口回归 | `python test/scripts/check_trpg_coc_api.py` | 全部通过（含「非法生活水平 400」） |
| AC06 全量回归 | `python -m pytest -q` | 全绿 |
| AC07 文档与归档 | `openspec validate coc-character-sheet --strict`；归档与实现同一 commit | `CHANGELOG [1.97.0]` 与 `BOTERO_VERSION` 一致 |
