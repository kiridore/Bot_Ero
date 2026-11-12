# 修复 COC 角色卡查看页

## Why

`/trpg/char/<用户>/<编号>` 的查看页（`webapp/static/char_view.js`）只实现了 DND 5E 渲染：读 `rules.attributes` / `rules.skills` / `char.level` / `char.ac` / `char.proficient_skills` 这些 DND 字段。COC 卡（1.66 起）虽然数据齐备并通过接口下发（`scores` / `skills` / `weapons` / `hp` / `max_san` / `mov` / `db` / `assets` …），但整页仍按 DND 渲染，于是等级显示 1、HP/AC 为 0、属性表空、技能表空——「几乎所有信息都没有正常显示」。

## What Changes

- 查看页按 `char.rules` 分支：`coc7th` 走新的 `renderCocView`，DND 卡保持原渲染不变。
- COC 视图内容与建卡页同口径：
  - 头部：`【姓名】职业` + 玩家名 + 年龄/性别/时代/住地
  - 状态行：HP 当前/上限、MP 当前/上限、SAN 当前/上限、MOV、伤害加值、体格、闪避、信用评级
  - 属性：3×3 排列（力量/敏捷/意志、体质/外貌/教育、体型/智力/幸运）
  - 技能：成长 / 职业 / 兴趣 / 成功率 + 成长标记 ✓
  - 武器：名称、类型、使用技能、成功率、伤害（含 DB 标注）、射程、次数、装弹量、故障值、贯穿
  - 资产、背景八项、克苏鲁神话、调查员笔记
- 修复接口断言：查看页依赖的公共卡片接口在回归脚本里按登录用户取卡。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：角色卡查看页的 COC 渲染。

## Scope and Compatibility

- 只改查看页渲染，不动接口与存储；DND 卡的显示完全不变。
- 未在查看页显示「您的角色可能」文案（建卡页才有），如需要可再加。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 COC 分支 | `node test/test_trpg_coc_view_dom.js` | `rules=coc7th` 的卡渲染出姓名/职业/年龄/时代/住地，DND 卡不出现「调查员笔记」等 COC 区块 |
| AC02 派生数值 | 同上 | 状态行含 `HP 8/10`、`SAN 40/99`、`MOV 9`、`+1D4`、`闪避 27`、`信用评级 40` |
| AC03 九项属性 | 同上 | 力量/敏捷/意志/体质/外貌/教育/体型/智力/幸运 全部出现 |
| AC04 技能与武器 | 同上 | 技能行含成功率与 ✓ 成长标记；武器行含类型、使用技能、装弹量、贯穿，伤害显示 `2D6+DB（DB=+1D4）` |
| AC05 背景与笔记 | 同上 | 资产（现金/消费水平/生活水平/克苏鲁神话）、背景八项、笔记均渲染 |
| AC06 接口契约 | `python test/scripts/check_trpg_coc_api.py` | 公共卡片接口返回 `rules=coc7th`、`scores.力量`、`skills`、`weapons`，且武器含 `type`/`skill` |
| AC07 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿；`CHANGELOG [1.77.2]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
