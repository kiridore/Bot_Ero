# 格斗 / 射击各专攻的基础成功率

## Why

`docs/COC7空白卡CY26.3.xlsx` 的技能表把武器技能拆成「射击：」+ 子技能（手枪 / 步枪·霰弹枪 / 冲锋枪 / 弓术 / 喷射器 / 机枪 / 重武器）与「格斗：」+ 子技能（斗殴 / 鞭子 / 电锯 / 斧 / 剑 / 绞具 / 链枷 / 矛），每个子技能的基础成功率不同（附表 C11:E13 用 IF 链写死了数值）。

我们的实现只在**裸技能名**（手枪 20、剑 20）上取得到值；写成新卡的自然写法 `射击:手枪`、`格斗:剑` 时基础值一律是 0。属于「玩家按新卡写法填，技能成功率凭空少 20~25 点」的静默错误。

## What Changes

- `core/trpg/coc.py` 新增附表数值表与别名：
  - `FIGHTING_SKILL_BASE`：斗殴 25、鞭子 5、电锯 10、斧 15、剑 20、绞具 15、链枷 10、矛 20
  - `FIREARM_SKILL_BASE`：手枪 20、步枪/霰弹枪 25、冲锋枪 15、弓 15、喷射器 10、机枪 10、重武器 10
  - `WEAPON_SPECIALTY_ALIASES`：弓术→弓、步枪 / 霰弹枪→步枪/霰弹枪、链锯→电锯
- 新增 `weapon_specialty()` / `weapon_specialty_base()`：拆出「类别:专攻」的专攻名并查表。
- `skill_base_map()` 把 `格斗:xxx`、`射击:xxx` 全部铺进基础值表（网页播种、`.ra`、武器成功率、finalize 兜底共用同一份）。
- `skill_base_for()` / `finalize()` 的兜底走专攻表；`skill_name_ok()` 接受附表写法（如裸写「弓术」）。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：武器技能基础成功率的取值口径。

## Scope and Compatibility

- 只影响「基础成功率」的计算，不改点数列，也不改已存的卡；打开旧卡会立刻显示正确的基础值。
- 未识别的专攻（如「射击:飞天」）仍按 0 处理，不报错。
- 无数据库变更；版本 1.95.0。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 专攻基础值 | `python -m pytest test/test_trpg_coc.py -q -k WeaponSpecialty` | 34 个「裸名 / 类别:专攻」组合都得到附表数值（手枪 20、步枪/霰弹枪 25、冲锋枪 15、弓 15、喷射器·机枪·重武器 10、斗殴 25、剑·矛 20、斧·绞具 15、电锯·链枷 10、鞭子 5） |
| AC02 名称合法 | 同上 | 上述写法 `skill_name_ok` 全部为真（含裸写「弓术」） |
| AC03 导出表 | 同上 | `skill_base_map()` 含 `射击:手枪` 20、`射击:重武器` 10、`格斗:剑` 20 |
| AC04 finalize | 同上 | 没写 base 的 `射击:步枪/霰弹枪` / `格斗:剑` / `射击:弓术` 分别补成 25 / 20 / 15 |
| AC05 未知专攻 | 同上 | `射击:飞天` 取 0 且 `weapon_specialty_base` 返回 None |
| AC06 武器库覆盖 | 手工脚本 | 武器库里 19 个使用技能全部取到非 0 基础值 |
| AC07 全量回归 | `python -m pytest -q` | 全绿 |
| AC08 文档与归档 | `openspec validate coc-character-sheet --strict`；归档与实现同一 commit | `CHANGELOG [1.95.0]` 与 `BOTERO_VERSION` 一致 |
