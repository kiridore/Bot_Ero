# 克苏鲁神话与信用评级不得获得成长标记

## Why

按规则（守密人核心规则书 5.11）「克苏鲁神话与信用评级永远不会获得技能成长标记，角色卡上也没有相应的方框」。核对代码发现两条路径违反了它：

- 我们的技能基础表把 `信用评级` 与 `克苏鲁神话` 也当成标准技能（各 39 项之一），`growth.mark()` 不区分，`.ra 信用评级` 成功就会打勾；实测卡上 `信用评级` 95% 时 `mark()` 返回 True。
- `settle()` 的「有技能达到 90% 或更高 → 当前 SAN +2D6」把这两项也计入触发条件——信用评级 95 会让玩家凭财富白拿 2D6 理智。

## What Changes

- `core/trpg/growth.py` 新增 `NO_GROWTH_SKILLS = {"克苏鲁神话", "信用评级"}` 与 `can_grow(name)`。
- `mark()` 对这两项直接返回 False。
- `settle()` 跳过这两项的成长检定（旧数据里的勾只清空、不结算），90% 理智奖励的触发条件也排除它们。
- `kb/DICE_GUIDE.md` 补一句说明。

## Capabilities

### Modified Capabilities

- `coc-skill-growth`：可打勾技能的范围与理智奖励触发条件。

## Scope and Compatibility

- 只影响这两项；其它技能打勾、结算、90% 奖励不变。
- 已有卡上若这两项带着勾，下次 `/跑团 成长` 会直接清掉、不涨点（符合规则）。
- 无数据库变更、无新增依赖；版本 1.84.1。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 不打勾 | `python -m pytest test/test_trpg_growth.py -q -k NoGrowth` | `mark("信用评级")`、`mark("克苏鲁神话")` 返回 False 且卡上无 `check` |
| AC02 不结算 | 同上 | 旧勾在 `settle()` 里不产生成长明细，结算后勾被清空、`growth` 仍为 0 |
| AC03 不发 SAN | 同上 | 信用评级 95% 不触发 +2D6（`san_change == 0`）；真实技能 95% 仍触发 |
| AC04 指令层 | `python -m pytest test/test_trpg.py -q` | `.ra 侦察` 成功后仍打勾 |
| AC05 全量回归 | `python -m pytest -q` | 全绿 |
| AC06 文档与归档 | `openspec validate coc-skill-growth --strict`；归档与实现同一 commit | `CHANGELOG [1.84.1]` 与 `BOTERO_VERSION` 一致 |
