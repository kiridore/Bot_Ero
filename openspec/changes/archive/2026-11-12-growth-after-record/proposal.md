# 录制结束后仍可结算幕间成长

## Why

所有者在问「录制结束前忘了成长，标记还在吗」时暴露出一个真实缺陷：**标记在，但结算被拦住**。

- 成长标记写在角色卡文件里（`skills.<技能>.check = true`），结束录制、暂停、重启都不会清，这点没问题。
- 但 `/跑团 成长` 有一层「本团规则必须是 COC 7th」的检查，而群规则存在 `pending.json` ——**开录成功时 `pending.json` 被删除**，于是结束后 `party.current_rule()` 回落到默认 `dnd5e`，任何后续成长都报「本团规则是 DND 5E，幕间成长需要 COC 7th」。

实测（本机）：录制中 `/跑团 成长` 正常；`/跑团 记录 结束` 之后同一条指令被拒。玩家只能等 DM 重新 `.dm` 并 `/跑团 规则 coc7th` 才能结算。

## What Changes

- `_handle_growth`：只在**本群正在录制**时按本团规则拦截（DND 团里不给 COC 卡结算）；不在录制中时以**角色卡自身规则**为准，不再看 `pending.json`。
- 测试：新增「结束录制后仍能结算」「录制中 DND 规则拒绝」两例；原「无录制时按群规则拒绝」改为「无录制时跟随卡片规则」。

## Capabilities

### Modified Capabilities

- `coc-skill-growth`：结算的规则门控范围。

## Scope and Compatibility

- 仅放宽「不在录制中」的判定；录制中行为不变（DND 团仍拒绝 COC 成长）。
- 不改任何持久化结构；`pending.json` 的清理逻辑保持不变。
- 无数据库变更、无新增依赖；版本 1.88.3。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 结束后可结算 | `python -m pytest test/test_trpg_session.py -q -k Growth` | 开录→结束（`current_rule` 已回落 dnd5e）后 `/跑团 成长` 正常结算并清空标记 |
| AC02 录制中仍门控 | 同上 | DND 录制中 COC 卡被拒「幕间成长需要 COC 7th」，标记保留 |
| AC03 无录制跟随卡片 | 同上 | 无录制、群规则未设置时，COC 卡照常结算 |
| AC04 全量回归 | `python -m pytest -q` | 全绿 |
| AC05 文档与归档 | `openspec validate coc-skill-growth --strict`；归档与实现同一 commit | `CHANGELOG [1.88.3]` 与 `BOTERO_VERSION` 一致 |
