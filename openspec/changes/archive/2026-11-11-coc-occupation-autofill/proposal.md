# 选择职业后自动补入本职技能

## Why

1.73 实现了「可选池显式选择」，但只处理了 **choices**（可选池）——职业的 **required（固定本职技能）** 从来没有被填进技能表。玩家选了「药剂师」，技能表还是空的，得自己逐个去添加「会计、急救、语言:拉丁语、图书馆使用、心理学」，而这恰恰是职业定义里已经写好的信息。等于建卡工具只做了「选」没做「填」。

## What Changes

- 新增纯函数 `requiredSkillNames(struct)`：返回固定本职技能并过滤掉 `类别:*` 通配项（通配要玩家自己填专攻）。
- 新增 `fillRequiredSkills(occ)`：把上述技能中技能表还没有的行补进去，基础值取技能表默认值；返回补入条数。
- 切换职业时先 `pruneAutoAdded()`：撤掉上一职业自动补进来、且成长/职业/兴趣点三列都还没填点数的行；填过点数的保留（避免误删玩家输入）。
- 选中职业后回执提示「已补入本职技能 N 项，可选池请逐项选择」，提示可选池仍需手动选。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：选职业时自动填充固定本职技能。

## Scope and Compatibility

- 通配项（`技艺:*`、`语言:*`、`射击:*` 等 81 条）不自动补——它们必须由玩家指定专攻。
- 可选池的选项仍不自动勾选（选择权在玩家），只在选中后补行。
- 已有卡片加载时不触发自动补（只在切换职业时触发），避免把玩家删掉的行又加回来。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 固定项过滤 | `node test/test_trpg_coc_skill_name.js` | `requiredSkillNames` 保留「会计」「科学:化学」，剔除 `技艺:*`；无职业时返回空数组 |
| AC02 自动补行 | `node test/test_trpg_coc_occupation_fill.js` | 选「药剂师」补入 3 行（会计/科学:化学/急救），不补通配项；重复调用补 0 行 |
| AC03 换职业清理 | 同上 | 未填点数的自动行被移除；填过兴趣点的行保留；换到另一职业补入其本职技能 |
| AC04 接线 | `python -m pytest test/test_trpg_coc.py -q -k occupation_fills` | 建卡页职业切换回调依次调用 `pruneAutoAdded()` 与 `fillRequiredSkills()` |
| AC05 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿；`CHANGELOG [1.76.2]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
