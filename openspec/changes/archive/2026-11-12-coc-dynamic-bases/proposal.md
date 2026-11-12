# 动态基础值（闪避/母语）与附表键规范化

## Why

1.80.3 把技能基础值收敛成一张静态表，但有两个技能的基础值本来就由属性决定：

- **闪避 = 敏捷 ÷ 2**：之前只在 `finalize` 与前端各写一段特例，`skill_base_map()` 里仍是 0；用统一表的地方（武器成功率、补行）会拿到 0。
- **母语 = 教育**：完全没进任何表，创建卡片后「母语」要么没有、要么 0。
- 附表里还有「学识：」「生存：」这类**带冒号结尾**的键，`skill_base_map()` 原样收了进去，查 `学识` 查不到。

## What Changes

- `core/trpg/coc.py`：新增 `DYNAMIC_BASES`（闪避→敏捷÷2、母语→教育）、`dynamic_skill_base()`、`skill_base_for(name, data)`；`finalize` 的存储值与兜底、`skill_defaults`、`growth.mark` 全部改走 `skill_base_for`；附表键统一 `rstrip("：:")`。
- options 下发 `dynamic_bases` 规则；前端 `skillDefaults` / `skillBaseFor` 按规则读属性输入框实时计算；重算时闪避与母语的基础值随属性刷新（原来只有闪避）。
- 母语进入默认补全（`finalize` 会补出 39 + 母语 = 40 项）。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：由属性派生的技能基础值。

## Scope and Compatibility

- 卡上存过的闪避/母语基础值一律被属性派生值覆盖（与闪避原有规则一致）。
- `finalize` 输出的技能数从 39 变为 40（多出母语）。
- 「学识：」「生存：」这类键在基础值表里规范化为「学识」「生存」；技能说明索引仍保留原始键以便按原名查说明。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 动态派生 | `python -m pytest test/test_trpg_coc.py -q -k DynamicBases` | `skill_base_for("闪避",{dex:55})=27`、`skill_base_for("母语",{edu:70})=70`、`会计=5` |
| AC02 finalize 忽略存储值 | 同上 | 卡上写 `闪避 base 0 / 母语 base 5`，DEX 80 / EDU 45 时 finalize 得 40 / 45 |
| AC03 成长补行 | 同上 | `growth.mark("母语")` 补出的 base = 教育值 |
| AC04 默认补全 | 同上 | `skill_defaults(55,70)` 的闪避 27、母语 70；finalize 技能数 = 39 + 1 |
| AC05 键规范化 | 同上 | 表里没有「学识：」「生存：」，但有「学识」1 与「生存」10 |
| AC06 前端 | `node test/test_trpg_coc_skill_defaults.js` | 母语随教育输入、闪避随敏捷输入；无输入时为 0 |
| AC07 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿；`CHANGELOG [1.80.4]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
