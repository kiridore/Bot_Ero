# 年龄调整：「不再提示」真正折叠面板 + 属性未掷时禁止应用

## Why

两个问题都出在「年龄调整」区块里：

1. `不再提示` 只写了 `{"kind":"skipped"}` 记录，面板照旧展开、两个按钮照旧在，并没有真的「不再提示」。
2. 属性还没掷/还没填（全是 0）时也能点应用：服务端只会报「教育扣减后为 0，属性不能低于 1」这种看不懂的错误，40–49 这类要分配体能扣减的年龄段甚至可能真的按 0 扣成负数再被拒。

## What Changes

- 前端：`skipped` 且年龄未变时，面板收成一行「已选择不套用年龄调整（40-49 岁）· 重新应用」；点「重新应用」展开完整面板（展开态提示「之前选过「不再提示」」）；年龄改到别的值自动展开。
- 前端 + 服务端：应用前检查该年龄段会动到的属性（体能项 + 外貌 + 教育）是否都已 > 0；未满足时按钮禁用并提示「先掷出或填写属性（力量、教育 还是 0）再应用」，服务端同样拒绝。
- 测试：`test_trpg_coc_age_dom.js` 补折叠/展开/自动展开/属性为 0 四组断言（共 28 项）；`test_trpg_coc_age.py` 补 3 例服务端守卫。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：年龄调整区块的交互与准入。

## Scope and Compatibility

- 不改规则计算、不改 `age_adjust` 记录结构、不改接口契约（`skip` 仍写同一条记录）。
- 已应用（`applied`）的卡行为不变。
- 版本 2.1.1。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 折叠 | `node test/test_trpg_coc_age_dom.js` | `skipped` 后只渲染一行说明 + 「重新应用」，没有 `ageApply` |
| AC02 展开 | 同上 | 点「重新应用」后出现完整面板与「之前选过「不再提示」」提示 |
| AC03 自动展开 | 同上 | `skipped(45)` 后把年龄改成 55，面板直接展开 |
| AC04 属性未填 | 同上 | 属性全空时 `ageApply.disabled === true`，提示含「先掷出或填写属性」与属性名 |
| AC05 服务端守卫 | `python -m pytest test/test_trpg_coc_age.py -q -k AttributesNotRolled` | 空属性 / 外貌为 0 / 已填属性三例 |
| AC06 全量回归 | `python -m pytest -q` | 全绿 |
| AC07 文档与归档 | `openspec validate coc-character-sheet --strict`；归档与实现同一 commit | `CHANGELOG [2.1.1]` 与 `BOTERO_VERSION` 一致 |
