# COC 武器表基础校验

## Why

武器表照抄人物卡原表（伤害写 `1D3+DB`、射程写 `15m`、次数写 `1(3)`），保留文本字段是设计；但目前**完全没有校验**：成功率能存 999 或 -5、故障值能写 abc、伤害能写「一点八」、武器名可空可重复、行数无上限。`core/trpg/coc.py` 里甚至没有 `weapons` 的任何处理，这批字段只存不用。

## What Changes

- 新增 `weapon_problems()` 并接入 `coc.validate()`（保存时 400，消息带武器名）：
  - 名称：必填、≤30 字、不区分大小写去重；
  - 成功率：0–99（空允许）；
  - 伤害：允许 `数字`、`NdM`、多项相加（`1D10+1D4`）、`DB`、`—`；其余拒绝；
  - 故障值：0–100 整数（或 `—`）；
  - 次数：`1` 或 `1(3)`；
  - 射程 ≤20、弹药 ≤10、贯穿 ≤10 字；最多 50 行。
- 前端输入框补 `min/max/maxlength/placeholder`（成功率 0–99、故障值改为数字框、伤害提示 `1D8 / 1D3+DB`）。
- 字段仍是自由文本（照原表），但不合格的文本会被拒绝，且错误消息直接由页面弹出（既有的 400 detail 透传）。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：武器表的取值校验。

## Scope and Compatibility

- 只加校验与输入框约束，不改存储结构（仍是 `list[dict]` 文本字段）。
- 不做「攻击宏」（`.atk` 命中 + 伤害联动），那是独立功能；本次只是让文本可被解析。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 合法武器 | `python -m pytest test/test_trpg_coc.py -q -k Weapons` | 原表示例（徒手 1D3+DB / 手枪 1D8 98 / 矛 1D10+1D4）全部通过 |
| AC02 伤害写法 | 同上 | `1D6`、`2d10`、`1D8+2`、`1D3+DB`、`DB`、`0`、`—`、空 通过；`一点八`、`D`、`1D`、`1D8+`、`+1D8`、`1D0`、`21D6` 拒绝 |
| AC03 其他字段 | 同上 | 空名、重名、超长名、成功率 999/-1、故障值 abc/101、次数「三连发」、射程 21 字、弹药 11 字、51 行均被拒 |
| AC04 接口 | `python test/scripts/check_trpg_coc_api.py` | 非法伤害 400（含「不是合法写法」）；重复武器 400（含「重复添加」）；合法武器仍 200 |
| AC05 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿；`CHANGELOG [1.71.5]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
