# 克苏鲁神话不是技能：从技能表移除，只留背景字段

## Why

克苏鲁神话在规则书里不是按技能点分配的技能（初始不能加点、成功后不成长、上限由它压 SAN），但我们的实现把它放在标准技能表 `SKILL_BASE` 里：

- 建卡页会给每张卡自动铺一行「克苏鲁神话 0%」，玩家可以往里填兴趣点；
- `finalize` 兜底铺满标准技能后，查看页、`/跑团 角色 查看`、记录快照里都会出现这一行；
- 卡片同时还有一个背景字段 `cthulhu_mythos`（`max_san = 99 − cthulhu_mythos` 用的就是它），两份数据并存，容易对不上。

## What Changes

- `core/trpg/coc_data.py`：`SKILL_BASE` 移除「克苏鲁神话」。
- `core/trpg/coc.py`：
  - `skill_base_map()` 跳过技能注释表里的「克苏鲁神话」（否则它会从 `SKILL_NOTES` 被重新加回来）。
  - `finalize()` 的技能循环跳过该名字，旧卡上残留的技能行不再渲染。
  - 新增 `normalize_mythos()`：保存时把旧卡技能行的点数折进 `cthulhu_mythos`（取较大值）并删除该行。
  - `skill_value()` 对「克苏鲁神话」返回背景字段的值，`.ra 克苏鲁神话` 继续可用。
- 建卡页：`mergeSkillDefaults` 丢弃该行；新增 `foldLegacyMythos`，打开旧卡时把技能行点数并进背景输入框（避免静默丢点）。
- 查看页：克苏鲁神话从「资产」行移到「背景」区块。
- `kb/DICE_GUIDE.md` 更新说明。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：克苏鲁神话的数据归属（背景字段）与旧数据迁移。

## Scope and Compatibility

- 旧卡：技能行的点数不会丢，保存或打开时折进背景字段（取较大值）；`max_san`、`.ra`、快照都改用背景字段，数值一致。
- 标准技能播种从 39 项变 38 项（`default_skills` 少一项）。
- 版本 2.3.0。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 不在技能表 | `python -m pytest test/test_trpg_coc.py -q -k mythos` | `default_skill_names()` 与 `skill_base_map()` 都不含「克苏鲁神话」 |
| AC02 不渲染旧行 | 同上 | `finalize` 的 `skills` 不含该名字，`max_san` 仍按 `cthulhu_mythos` 计算 |
| AC03 `.ra` 仍可用 | 同上 | `skill_value(card, "克苏鲁神话")` 返回背景字段值 |
| AC04 旧卡迁移 | 同上 | `validate` 后技能行消失、背景字段取较大值 |
| AC05 播种数量 | `python test/scripts/check_trpg_coc_api.py` | `default_skills` 38 项且不含该名字，`skill_base` 也不含 |
| AC06 页面 | `node test/test_trpg_coc_*.js` + `test_trpg_coc_view_dom.js` | 13 个 COC 用例全过；查看页把克苏鲁神话放进背景 |
| AC07 全量回归 | `python -m pytest -q` | 全绿 |
| AC08 文档与归档 | `openspec validate coc-character-sheet --strict`；归档与实现同一 commit | `CHANGELOG [2.3.0]` 与 `BOTERO_VERSION` 一致 |
