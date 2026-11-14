# 选职业后自动填充信用评级

## Why

按 1.94.0 的规则，选职业时应把信用评级的「职业点」补到职业下限。实际用起来填不上，三个原因：

1. **职业没变就早退**：换职业的处理器里有 `if (occ.name === lastOccupation) return;`，而 `lastOccupation` 在 `bind()` 时就取了当前职业名。卡片上已有职业时，再选同一个职业（或下拉框重新提交同一个值）直接返回，补下限的代码根本没机会跑。
2. **旧卡不补**：1.94.0 之前信用评级只存在资产区字段（`credit_rating`），技能行是 0。服务端只在**保存**时迁移，页面加载时既不迁移也不补下限，于是编辑一张旧卡看到的技能行和资产区都是空的。
3. **技能行可能不存在**：极旧的卡技能表里没有「信用评级」行，补下限直接跳过。

## What Changes

- `webapp/static/trpg_coc.js` 新增 `ensureCreditRow()` / `fillCreditFloor(occ)` / `seedCreditFromAsset()`：
  - 缺「信用评级」行时先补一行；
  - 选到正式职业且技能行合计为 0 时，把职业下限写进「职业」列并同步资产区；
  - 旧卡（技能行为 0、资产区有值）按「下限记职业点、其余记兴趣点」铺进技能行，与保存时的服务端迁移口径一致。
- 职业变更处理器把补下限挪到「职业没变就早退」之前；职业没变但补了下限时也会刷新派生值。
- `init()` 在 `render()` 之后调用 `seedCreditFromAsset()` + `fillCreditFloor()`，打开旧卡就能看到正确的金额。
- 新增 `test/test_trpg_coc_credit_fill.js`（12 项，真实执行上述函数）与一条接线守卫；`TestOccupationSearch` 的断言改为「补下限发生在早退之前」。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：选职业时的信用评级填充与旧卡加载口径。

## Scope and Compatibility

- 只改前端展示与预填，不写库；保存时服务端的 `normalize_credit_rating()` 仍会做最终归一化。
- 已有加点的卡不会被覆盖（合计 > 0 时两处都跳过）。
- 无数据库变更；版本 1.96.2。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 补下限 | `node test/test_trpg_coc_credit_fill.js` | 药剂师（下限 35）→ 职业点列 35、资产区 35、合计列 35 |
| AC02 不覆盖 | 同上 | 已有职业点 40 + 兴趣 5 时再选职业，职业点仍是 40 |
| AC03 旧卡迁移 | 同上 | 资产区 45 + 技能行 0 → 职业 35 / 兴趣 10，资产区仍 45 |
| AC04 无职业 | 同上 | 没有职业时旧值 20 全部记兴趣点，职业点保持 0 |
| AC05 不重复迁移 | 同上 | 技能行已有加点时不再把资产区旧值搬进来 |
| AC06 接线 | 同上 | 源码中 `fillCreditFloor(occ)` 出现在 `if (occ.name === lastOccupation)` 之前；`init()` 里 `render()` 之后有 `seedCreditFromAsset()` + `fillCreditFloor()` |
| AC07 全量回归 | `python -m pytest -q` | 全绿（含 DOM 套件自动发现新用例） |
| AC08 文档与归档 | `openspec validate coc-character-sheet --strict`；归档与实现同一 commit | `CHANGELOG [1.96.2]` 与 `BOTERO_VERSION` 一致 |
