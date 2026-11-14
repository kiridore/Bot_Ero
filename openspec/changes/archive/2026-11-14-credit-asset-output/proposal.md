# 资产区信用评级改成只读展示

## Why

资产区的信用评级虽然是 `readonly` 的输入框，外观上仍是可填的输入框（带数字步进箭头、白底边框），玩家会以为这里能改；而且这个只读框还挂着一个 `change` 监听，逻辑上像「可以输入」。

## What Changes

- 资产区的信用评级从 `<input readonly>` 改成 `<output>`（只读展示，`.coc-readonly` 灰底样式，没有边框与步进箭头），值始终来自技能表。
- `syncCreditAssets()` 改为写 `textContent`；「按规则填入」与资产提示都直接调用 `creditFromSkillRow()`，不再经过那个输入框。
- 生活水平跟随规则收敛为一处：`syncCreditAssets()` 里「还没选过才跟随」——避免玩家手选过又被改掉。
- 删掉 `credit_rating` 的 `change` 监听（已无输入来源），并修掉它引用的旧 id `life_level`（实际元素是 `living_standard`）。
- 测试：`TestCreditSkillUi` 断言 `<output>` 且无 `<input id="credit_rating">`；`test_trpg_coc_credit_fill.js` 的桩改为 output，新增「资产区不是输入框」断言。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：资产区信用评级的呈现方式。

## Scope and Compatibility

- 纯前端展示；数据来源、校验、服务端归一化都不变。
- 生活水平的选择仍可手动修改，只是不再被信用评级覆盖。
- 无数据库变更；版本 1.96.4。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 只读展示 | `python -m pytest test/test_trpg_coc.py -q -k CreditSkillUi` | 源码含 `<output id="credit_rating"`，不含 `<input id="credit_rating"` |
| AC02 同步 | `node test/test_trpg_coc_credit_fill.js` | 补下限后 `#credit_rating` 的 `textContent` 为 35；旧卡迁移后为 45 |
| AC03 无输入监听 | 同上 / 源码守卫 | 源码里不再有 `getElementById("credit_rating").addEventListener` |
| AC04 按规则填入 | 源码守卫 | `fillAssets` 里 `const credit = creditFromSkillRow();` |
| AC05 全量回归 | `python -m pytest -q` | 全绿 |
| AC06 文档与归档 | `openspec validate coc-character-sheet --strict`；归档与实现同一 commit | `CHANGELOG [1.96.4]` 与 `BOTERO_VERSION` 一致 |
