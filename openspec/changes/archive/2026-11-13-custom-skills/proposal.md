# 技能名自由填写：认识的自动带基础值，不认识的开放基础值

## Why

建卡页的「添加技能」挂着官方技能下拉候选，并且只接受官方名或「类别:专攻」写法——想加一个规则书外/自制专攻，输入框直接拒绝。而服务端同样把不认识的技能名在 finalize 里静默丢掉，等于「页面能看见、游戏里用不了」。

## What Changes

- 建卡页去掉 `<datalist>` 下拉候选（`list="skillOptions"`），输入框接受任意字符串：认识的技能自动填基础值，不认识的基础值从 0 开始、可手填；提示语改为「不是官方技能，基础值可自行填写」；仍然拦空名、超过 30 字、重名。
- `core/trpg/coc.py`：
  - `skill_name_ok()` 放宽为「非空、≤30 字、无换行制表符」——自定义技能合法。
  - `finalize()` / `.ra` / `/跑团 成长` 一并对自定义技能生效（基础值取卡上填的，可打成长标记）。
  - 新增 `is_known_skill()`：判断技能是否在规则表里（官方项、`类别:专攻`、武器专攻）；职业可选池校验改用它，仍然拒绝凭空的技能名。
  - `validate()` 新增技能名合法性检查，名字不合规（如超长）会明确报错，而不是保存后消失。
- `normalizeSkillName()` 只做别名与「类别:专攻」归一，不再返回 null。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：技能名的接受范围与基础值来源。

## Scope and Compatibility

- 自定义技能不能占用职业点（不是本职技能），只能用兴趣点/成长——与既有规则一致。
- 职业可选池仍只接受规则表内的技能名（`is_known_skill`）。
- 旧卡不受影响；名字超过 30 字的卡保存时会收到明确错误提示。
- 无数据库变更；版本 1.96.0。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 无下拉 | `python -m pytest test/test_trpg_coc.py -q -k add_skill` | 源码含 `id="skillName"`、不含 `list="skillOptions"`、不含 `<datalist` |
| AC02 归一化放行 | `node test/test_trpg_coc_skill_name.js` | 「飞天」→「飞天」、「  飞天  」→「飞天」、官方名与类别写法照旧、空串→`""` |
| AC03 服务端保留 | `python -m pytest test/test_trpg_coc.py -q -k custom_skill` | `finalize` 保留「飞天」35%、`skill_value` 35、`is_known_skill` 为假 |
| AC04 成长 | `python -m pytest test/test_trpg_growth.py -q` | 自定义技能打勾成功、基础值为 0 |
| AC05 可选池仍严 | `python -m pytest test/test_trpg_coc_occupations.py -q -k unknown` | 可选池填「飞天」仍报「不在技能表内」 |
| AC06 接口 | `python test/scripts/check_trpg_coc_api.py` | 自定义技能 200 且保留 35；超长技能名 400 |
| AC07 全量回归 | `python -m pytest -q` | 全绿 |
| AC08 文档与归档 | `openspec validate coc-character-sheet --strict`；归档与实现同一 commit | `CHANGELOG [1.96.0]` 与 `BOTERO_VERSION` 一致 |
