# COC 技能名前端校验与去重

## Why

建卡页「添加技能」是自由文本框，前端不做任何校验，但服务端 `finalize()` 会用 `skill_name_ok()` 静默丢弃不认识的技能名——结果是**编辑页看得见、机器人看不见**：成功率不算、职业点不计、`.ra` 找不到，且一句提示都没有。另外同名技能可重复添加，保存时被 dict 覆盖，静默丢一行。

## What Changes

- 新增前端规范化 `normalizeSkillName()`：别名归一（侦查→侦察）、官方技能名原样保留、`类别:专攻` 写法保留并统一半角冒号、漏写分隔符自动补（科学生物学 → 科学:生物学）、纯类别与凭空造名返回 null。
- 「添加技能」时校验名字，不合法当场提示并拒绝；同名（按别名归一后比较）提示「技能已存在」并拒绝。
- `/api/trpg/coc/options` 增加 `skill_aliases`，让前端与服务端共用同一份别名表，避免两套标准。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：技能录入的技能名校验与去重。

## Scope and Compatibility

- 只加前端校验与一个只读字段（`skill_aliases`），不改保存结构、不改服务端校验口径。
- 前端比服务端严格一档：服务端仍接受「科学」这类纯类别名前缀（`startswith`），前端拒绝纯类别（无专攻名时没有意义），老数据不受影响。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 规范化行为 | `node test/test_trpg_coc_skill_name.js` | 官方名与别名通过；`科学:生物学`、全角冒号、漏分隔符均归一到 `科学:专攻`；纯类别与凭空造名返回 null |
| AC02 录入拦截 | 人工看 `/trpg/coc` | 添加「飞天」被拒并提示；重复添加「侦查」与已有「侦察」被拒 |
| AC03 数据源 | `python test/scripts/check_trpg_coc_api.py` | 选项接口返回 `skill_aliases`，`侦查 → 侦察` |
| AC04 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿（含新增 JS 用例）；`CHANGELOG [1.71.4]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
