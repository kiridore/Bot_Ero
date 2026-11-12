# 补上默认技能的成长标记、武器技能基础值与共享资产合计

## Why

对 1.80.1 做完整性审计时实测出三个问题：

1. **默认技能的成长标记打不上**：1.79.0 让卡上没有的技能也能 `.ra`（默认值兜底），但 `growth.mark()` 只认卡上真实存在的行，返回 False 且无任何提示——玩家用默认技能成功检定拿不到成长机会。
2. **武器技能仍然 `.ra` 不了**：`斗殴`、`手枪`、`步枪/霰弹枪` 等是规则书里的合法技能名，但不在 39 项标准技能里，`.ra 斗殴` 直接报「角色卡里没有技能」。附表其实给了它们的基础值（斗殴 25%、手枪 20%…）。
3. **资产合计写了两遍**：建卡页 `assetsTotal()` 与查看页 `reduce` 各自算一份，口径迟早漂移。

## What Changes

- `core/trpg/growth.py`：`mark()` 在卡上没有该技能行时，按规则补一行再打勾——基础值优先取附表（`科学:化学` 1%），其次武器技能表（`斗殴` 25），都没有则留空由 `finalize` 兜底；未知技能仍返回 False。
- `core/trpg/coc.py`：
  - `weapon_skill_base()`：从武器库用到的技能 + 附表基础值推导武器技能表（19 项，含 `弓术→弓` 的别名）。
  - `skill_value()`：卡上没有该技能时回落到武器技能基础值。
  - `skill_name_ok()`：接受武器技能名（否则 `finalize` 会丢弃这些行）。
- `core/web/static/trpg_assets.js`：资产合计唯一实现（现金 + 五类，含中文单位的文本金额按 0），建卡页与查看页都改用它。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：技能默认值的成长标记、武器技能可用性、资产合计的单一来源。

## Scope and Compatibility

- 武器技能**不会**被加进每张卡的技能表（39 项不变），只在 `.ra` 查询与打勾补行时生效。
- `skill_name_ok` 放宽后，卡片上可以存 `斗殴` 这类行；`finalize` 会正常计算它们。
- 资产合计口径变化：中文单位文本（「5先令」「2镑10先令」）按 0 计，不再被误读成 5。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 武器技能基础值 | `python -m pytest test/test_trpg_coc.py -q -k WeaponSkills` | 斗殴 25、手枪 20、步枪/霰弹枪 25、弓 15、绞具 15，表内 ≥15 项 |
| AC02 武器技能可用 | 同上 | `.ra 斗殴` = 25、`弓术` 经别名 = 15、未知技能仍为 None；`skill_name_ok("斗殴")` 为真 |
| AC03 成长标记补行 | `python -m pytest test/test_trpg_coc.py -q -k GrowthMarkDefaults` | 卡上没有「会计」时 mark 成功并补 base=5；「科学:化学」补 base=1；别名命中已有行不重复添加；未知技能拒绝 |
| AC04 武器技能标记 | 同上 | `growth.mark("斗殴")` 成功，`finalize` 得出 25 |
| AC05 共享资产合计 | `node test/test_trpg_coc_assets.js`；`node test/test_trpg_coc_view_dom.js` | 合计、带符号金额、文本金额按 0、空值安全；查看页仍显示 420000 |
| AC06 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿；`CHANGELOG [1.80.2]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
