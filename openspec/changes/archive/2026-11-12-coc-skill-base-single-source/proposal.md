# 技能基础值收敛到单一来源

## Why

技能基础值同时存在「读时兜底」和「建卡播种」两条路径，而且各自查不同的表，实测同一技能会得出三个不同答案：

```
科学:化学   存储空行=0 ｜ 缺行默认=None ｜ mark 补行=1 ｜ 附表=1%
技艺:表演   存储空行=0 ｜ 缺行默认=None ｜ mark 补行=5 ｜ 附表=5%
斗殴        存储空行=0 ｜ 缺行默认=None ｜ mark 补行=25｜ 附表=25%
会计        存储空行=5 ｜ 缺行默认=5     ｜ mark 补行=5 ｜ 附表=5%   ← 只有标准技能一致
```

根因是四张表各说各话：`SKILL_BASE`（39 项标准）、`SKILL_NOTES`（附表 110 项）、`weapon_skill_base()`（19 项武器技能）、前端 `options.skill_base`（只发 39 项）。前端播种与补行拿 `options.skill_base[name] || 0`，于是专攻与武器技能一律被填成 0。

## What Changes

- 新增 `core/trpg/coc.py::skill_base_map()`：**唯一来源**——标准 39 项 + 附表专攻（41 项）+ 武器技能（19 项），统一 canonical 名与译名。`finalize` 的兜底、`growth.mark` 的补行、前端所有查值都改用它。
- 新增 `default_skill_names()`：明确「建卡时铺进技能表」的只有 39 项标准技能（专攻与武器技能不铺，避免每张卡多出几十行）。
- options 下发 `skill_base`（统一表）+ `default_skills`（播种名单）；前端 `skillDefaults` 按名单播种，`skillBaseFor()` 统一查值（含专攻与武器技能）。
- 武器表播种成功率、职业可选池补行、手动添加技能、职业技能自动补入四处都改用 `skillBaseFor()`。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：技能基础值的单一来源与播种范围。

## Scope and Compatibility

- 播种范围不变（仍是 39 项 + 闪避按敏捷）；只是数值改由统一表提供，专攻/武器技能不再被填成 0。
- 卡片上已存的 `base` 仍然优先（玩家手改过的值不会被覆盖）。
- `finalize` 的默认补全范围不变（仍只补 39 项标准技能）。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 统一表 | `python -m pytest test/test_trpg_coc.py -q -k SkillBaseConsistency` | 表 ≥100 项，含会计 5、科学:化学 1、斗殴 25 |
| AC02 三路径一致 | 同上 | 对 5 个代表技能，`finalize(存储空行)` 与 `growth.mark` 补出的 base 都等于统一表 |
| AC03 播种范围 | 同上 + `check_trpg_coc_api.py` | `default_skill_names()` 恰 39 项且不含专攻/武器技能；options 的 `default_skills` 同步 |
| AC04 前端查值 | `node test/test_trpg_coc_skill_defaults.js`、`node test/test_trpg_coc_occupation_fill.js` | 播种只铺标准技能；补行用 `skillBaseFor`（专攻 1、武器 25） |
| AC05 闪避不受影响 | 同上 | 闪避基础值仍为敏捷/2 |
| AC06 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿；`CHANGELOG [1.80.3]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
