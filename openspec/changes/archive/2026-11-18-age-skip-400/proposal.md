# 「不再提示」点了不折叠：接口被整卡校验挡住

## Why

2.1.1 把「不再提示」做成折叠，但用户实测点了没反应。根因不在前端折叠逻辑，而在保存接口：

`POST /api/me/characters/{id}/age-adjust` 统一走 `_age_adjust_save()`，它先跑**整卡** `validate()`。而点「不再提示」的时机，玩家往往还在建卡中途——信用评级还没到职业下限、可选池没选满、点数刚超预算——这些都会让 `validate()` 返回 400，前端收到错误只弹一句 toast，`afterAgeAdjust()` 不执行，`card.age_adjust` 不更新，面板自然一直展开。

实测（45 岁、猎人、信用评级 0、其余属性已填）：

```
POST /age-adjust {"action":"skip"} → 400 信用评级应在 20-50 之间（当前 0）
```

## What Changes

- `webapp/trpg/app.py::_age_adjust_save`：不再跑整卡 `validate()`，只跑 `age_adjust_problems()`（年龄范围、`age_adjust.age` 与卡片年龄一致、体能分配与记录一致）。年龄调整本身不改变职业点、可选池、信用评级，没必要让这些挡住它；结构性问题留给下一次正常保存。
- 测试：`test_trpg_coc_age.py::TestAgeAdjustOnIncompleteCard` 3 例——不完整卡上 `skip` 成功并写入记录、`apply` 成功、并断言同一张卡 `validate()` 确实会因信用评级被拒（说明为什么要收窄校验）。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：年龄调整接口的校验范围。

## Scope and Compatibility

- `apply` 的算术校验不变（属性不能扣到 0 以下、体能合计必须等于配额），只是不再因为别处的合规问题被拒。
- 记录结构、前端交互、`age_adjust_problems` 的规则一致性强校验都不变。
- 版本 2.1.3。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 空卡也能跳过 | `python -m pytest test/test_trpg_coc_age.py -q -k IncompleteCard` | 信用评级 0 的卡调用 `skip` 成功，写入 `{"kind":"skipped","age":45,"band":"40-49"}` |
| AC02 空卡也能应用 | 同上 | 同卡 `apply` 成功，力量 55→50、外貌 50→45 |
| AC03 证明旧行为会拦 | 同上 | 同一张卡 `coc.validate()` 返回信用评级问题 |
| AC04 全量回归 | `python -m pytest -q` + `python test/scripts/check_trpg_coc_api.py` | 全绿 |
| AC05 文档与归档 | `openspec validate coc-character-sheet --strict`；归档与实现同一 commit | `CHANGELOG [2.1.3]` 与 `BOTERO_VERSION` 一致 |
