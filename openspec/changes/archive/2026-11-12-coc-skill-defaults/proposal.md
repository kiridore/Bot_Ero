# COC 技能默认值兜底与允许无职业建卡

## Why

按规则每个技能都有基础成功率，但实现上：

1. **默认值不落盘也不兜底**：新卡只种 4 项技能（侦查/聆听/图书馆使用/闪避），`finalize()` 只遍历卡上已有的技能行。结果卡上没有的标准技能（会计 5、急救 30…共 39 项）在查看页、`.ra` 里全部不存在——`.ra 会计` 直接报「角色卡里没有技能」。
2. **闪避口径错**：`SKILL_BASE["闪避"] = 0`，而规则是 DEX/2；卡上存了 `闪避: {base: 0}` 就按 0 算，`.ra 闪避` 得到 0 而不是 27。
3. **未选职业存不了**：`validate()` 里硬性 `请选择职业`，与「未选职业也应按默认值玩」的规则冲突。

## What Changes

- `core/trpg/coc.py`：
  - 新增 `skill_defaults(dex_score)`：技能表全部标准技能的默认基础值，闪避取 `DEX//2`。
  - `finalize()`：闪避的基础值一律按 `DEX//2`（忽略卡上存的值）；卡上没写过的标准技能补出 `{base, 0, 0, 0}` 行，因此 `skill_value()`/`.ra`/查看页自动获得默认值。
  - `validate()`：去掉「请选择职业」；未选职业时职业点必须为 0（报「未选择职业时不能分配职业点」）。
- 建卡页：加载卡片时把默认技能与卡上已有技能合并（已有值优先），闪避基础值随敏捷实时刷新。
- 新增测试：`skill_defaults`/默认值进入 finalize/已存技能覆盖默认/闪避按敏捷/未知技能仍缺失；JS 侧 `skillDefaults`/`mergeSkillDefaults`；API「未选职业可保存」「无职业不能加职业点」「默认技能进接口」。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：技能默认值、闪避口径、职业可选。

## Scope and Compatibility

- **不写盘**：默认值在读时补出，卡文件不因本变更膨胀；编辑页合并默认值后保存会把完整技能表写入卡片（首次保存后即自描述）。
- 闪避的基础值改为由敏捷派生：卡上手动改过的闪避 base 会被覆盖（成长/职业/兴趣点仍保留）。
- 未选职业的卡：职业点预算为 0，职业点为 0 才可保存；信用评级不再做职业区间校验。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 默认值表 | `python -m pytest test/test_trpg_coc.py -q -k SkillDefaults` | `skill_defaults(55)` 中会计 5、侦察 25、急救 30、闪避 27；未知技能仍为 None |
| AC02 读时兜底 | 同上 | `finalize(skills={})` 含全部 39 项标准技能且急救 total=30；已有技能行的点数覆盖默认值 |
| AC03 闪避口径 | 同上 | 卡上写 `闪避 base 0` 时 finalize 仍为 27；DEX=80 时 base=40 |
| AC04 无职业建卡 | `python -m pytest test/test_trpg_coc.py -q -k occupation`；`python test/scripts/check_trpg_coc_api.py` | 无职业可保存（`validate` 无问题）；无职业时加职业点返回 400 |
| AC05 页面默认技能 | `node test/test_trpg_coc_skill_defaults.js` | `skillDefaults` 覆盖整张技能表、闪避按敏捷；`mergeSkillDefaults` 保留已存点数并存表外技能 |
| AC06 接口 | `python test/scripts/check_trpg_coc_api.py` | 查看接口返回 ≥39 项技能，急救 30、闪避 = DEX/2 |
| AC07 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿；`CHANGELOG [1.79.0]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
