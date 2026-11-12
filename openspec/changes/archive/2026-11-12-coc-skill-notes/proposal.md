# 技能说明图标

## Why

新卡在「附表」B95:K212 为每个技能列了详细说明（技能注释、基础值、特殊适用），「技能注释」工作表只是它的查询界面。我们的建卡页与查看页都只显示技能名与成功率，玩家要理解某项技能做什么得另翻规则书。

## What Changes

- 新增 `core/trpg/skill_notes.py`：从附表抄录 110 条技能说明（名称/基础值/特殊适用/注释），子项（技艺·格斗·射击·科学）按「类别:名称」建键。
- `core/trpg/coc.py::skill_note_index()`：把附表里的旧译名对齐到角色卡规范名（取悦→魅惑、侦查→侦察、导航→领航、计算机使用→计算机使用 Ω、艺术与手艺→技艺）。
- `webapp/trpg/app.py`：options 下发 `skill_notes`；新增 `GET /api/trpg/coc/skill-notes` 供查看页按需加载。
- 建卡页与查看页的技能名后加 `ⓘ` 图标（`title` 为注释正文 + 基础值/特殊适用），无说明的技能不显示图标；专攻名没有独立说明时回落到类别说明。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：技能说明的展示。

## Scope and Compatibility

- 说明文本照抄附表，含原文的换行与项目符号。
- 「技能注释」工作表里的成功等级解释（0–500 分档）与可选规则**未接入**，本次只做逐技能说明。
- 图标用原生 `title` 气泡，不引入额外 JS 组件。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 索引完整 | `python -m pytest test/test_trpg_coc.py -q -k SkillNotes` | 39 项基础技能全部有说明；魅惑/侦察/领航/计算机使用 Ω 通过别名命中；技艺:表演、科学:化学、技艺 均有条目；`会计` 基础值 5% |
| AC02 接口 | `python test/scripts/check_trpg_coc_api.py` | options 的 `skill_notes` ≥100 条；`/api/trpg/coc/skill-notes` 返回同样数量 |
| AC03 查找规则 | `node test/test_trpg_coc_skill_notes_dom.js` | 精确命中、专攻子项、类别回落、去前缀命中、无说明返回 null；title 含正文与基础值 |
| AC04 页面 | 人工看 `/trpg/coc` | 技能名后有 ⓘ，悬停显示该技能注释；无说明的技能没有图标 |
| AC05 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿；`CHANGELOG [1.80.1]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
