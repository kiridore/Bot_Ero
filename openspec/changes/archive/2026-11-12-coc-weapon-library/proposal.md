# 武器表对齐新版人物卡并接入武器库

## Why

所有者提供了更完整的人物卡 `docs/COC7空白卡CY26.3.xlsx`。对照后发现两处差距：

1. **字段不全**：新卡武器表有「类型」（常规武器/手枪/步枪…）与「使用技能」（斗殴/手枪/步枪-霰弹枪…）两列，我们的武器行没有；「装弹量」还被叫作「弹药」。
2. **录入全靠手打**：新卡附带一张「武器列表 战斗」工作表（104 条可用武器，含伤害/射程/贯穿/每轮/装弹量/故障值/时代），现在玩家必须逐字段抄。
3. **`+DB` 无法理解**：伤害写作 `1D6+DB`、`1D3+半DB`，但界面上没有任何地方告诉玩家当前角色的 DB 是多少。

`.atk` 攻击指令本次**不做**（所有者决定）。

## What Changes

- 新增 `core/trpg/weapon_data.py`：104 条武器库，抄自新卡「武器列表 战斗」，字段与列一一对应（`*` 罕见 / `-` 不合时代已剥离为布尔标记）。
- 武器行新增「类型」「使用技能」两列，「弹药」更名为「装弹量」；使用技能为必填且必须能在技能表或武器库技能里找到。
- `/api/trpg/coc/options` 下发 `weapon_library`；建卡页增加「从武器库选择…」下拉，按卡上「时代」筛选（1920s / 现代），选中即整行填充（成功率取技能表当前值）。
- 伤害校验放宽到新版卡的真实写法：`+半DB`、`1D6+燃烧`、`2D6/1D6/1D3`（霰弹分档）、`4D10/5码`（爆破半径）、`眩晕` 等；要件不变（拒绝 `1D8+`、`+1D8`、`1D`、`一点八` 这类）。
- 次数校验支持 `1/2`（每两轮一次）、`1 or 2`、`1(2)or连射`、`全自动`、`布置`。
- 伤害含 DB 时在页面「实际伤害」列与 `/跑团 角色 查看` 中标注当前值：`1D6+DB（当前 DB=1D4）`，DB 变了标注自动跟着变。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：武器字段、武器库、伤害与次数的可接受写法、DB 标注。

## Scope and Compatibility

- 武器不参与掷骰（`.atk` 未实现），DB 标注纯展示。
- 已有卡片没有 `type` / `skill` 字段：保存时会因「缺少使用技能」被拒，需在建卡页补一次（当前环境无生产旧卡）。
- 武器库注释列在源表里行位错位，本次不导入注释。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 武器库数据 | `python -m pytest test/test_trpg_coc.py -q -k weapon_library` | 武器库 ≥100 条，且每一条都能通过 `weapon_problems` |
| AC02 新字段校验 | 同上 `-k "skill or type"` | 缺使用技能报「缺少使用技能」；技能名不在表内报「不在技能表里」；斗殴/手枪/步枪-霰弹枪/射击:手枪/格斗:斗殴 通过；类型超 10 字报错 |
| AC03 伤害写法 | `python -m pytest test/test_trpg_coc.py -q -k damage` | `1D6+半DB`、`2D6/1D6/1D3`、`4D10/5码`、`眩晕`、`1D6+燃烧` 通过；`1D8+`、`+1D8`、`1D`、`一点八` 仍被拒 |
| AC04 时代筛选 | `node test/test_trpg_coc_weapon_era.js` | 1920s 卡接受 1920s 与多标签武器、拒绝仅现代与罕见；现代卡反之；时代为空不筛选 |
| AC05 接口 | `python test/scripts/check_trpg_coc_api.py` | options 下发 ≥100 条武器库且字段齐全；建卡回传 type/skill；非法或缺失使用技能返回 400 |
| AC06 DB 标注 | `python -m pytest test/test_trpg_coc.py -q -k db_annotation` | `1D6+DB` 标注为 `1D6+DB（当前 DB=1D4）`，无 DB 的伤害不加标注 |
| AC07 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿；`CHANGELOG [1.77.0]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
