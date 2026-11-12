# 角色卡展示职业详情

## Why

雪家卡（`docs/COC7空白卡CY26.3.xlsx`「职业列表」）除名称、信用评级、技能点公式之外，还有 **K 列推荐关系人**与 **M 列职业介绍**（这段文字描述这个职业在世界上是什么样的人）。我们只抄了前几项，角色卡查看页只显示「【姓名】职业」一行，玩家看不到本职技能清单、可选池选了什么、这个职业具体是什么。

## What Changes

- 新增 `core/trpg/occupation_details.py`：113 个职业的「推荐关系人」「职业介绍」，按我们既有的职业序号建键；新卡改过名的 5 个职业按别名表匹配（中介调查员→事务所侦探·保安 等）。
- `coc.py::occupation_by_name()` 合并 `contacts` / `description` 两个字段（`/api/characters/...` 已经下发 `occupation_info`，前端自动拿到）。
- options 接口的职业列表也带上这两列（建卡页将来可用）。
- 角色卡查看页新增「职业」区块：`职业名 · 信用评级区间 · 技能点公式`、职业介绍、本职技能（散文）、可选池已选、推荐关系人、职业点与兴趣点用量。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：职业详情的展示。

## Scope and Compatibility

- 纯展示，不改职业数据本体（名称/区间/公式/正确答案都以 `coc_data.OCCUPATIONS` 为准）；新卡比我们多 116 个职业、且个别职业改名，本次**不合并职业列表**。
- 「管家、男仆、女仆」在新卡里没有介绍与关系人，字段为空，页面自动省略。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 数据 | `python -m pytest test/test_trpg_coc.py -q -k OccupationDetails` | 会计师含「生意伙伴」与「会计师可能在企业工作」；中介调查员经别名匹配到内容；未知职业返回 None；除「管家、男仆、女仆」外全部职业都有详情 |
| AC02 接口 | `python test/scripts/check_trpg_coc_api.py` | options 的职业项带 `description` 与 `contacts` |
| AC03 页面 | `node test/test_trpg_coc_view_dom.js` | 查看页出现「药剂师 · 信用评级 30-70 · 技能点 教育×4」、职业介绍、本职技能、可选池已选、推荐关系人、职业点用量 |
| AC04 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿；`CHANGELOG [1.82.0]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
