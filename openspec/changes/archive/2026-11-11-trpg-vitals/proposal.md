# 跑团数值变动与 COC 理智检定

## Why

跑团过程中最常做的两件事——扣血和过理智检定——目前完全没有：DND 卡有 `current_hp` 字段却没有任何指令能改，COC 卡连"当前值"都没有（`hp/mp/san` 都是派生上限）。DM 只能在群里口述、玩家自己心里算。

## What Changes

- 新增插件 `trpg_vitals`，提供三条指令：
  - `.hp <±值|满> [@人]`：两套规则通用
  - `.san <±值|满> [@人]`：COC 卡
  - `.sc <成功损失>/<失败损失>`：COC 理智检定，例 `.sc 1/1d6`
- 支持骰子表达式（`.hp -1d6`）；下限截断 0 并提示状态，上限截断到卡片上限，`满` 回满。
- 权限：本人可改自己；DM 或超级用户可用 @ 指定他人。
- 规则一致性：卡片规则须与本团规则一致，否则拒绝（与 `/跑团 准备` 同一口径）。
- COC 卡新增持久字段 `current_hp` / `current_mp` / `current_san`（缺省 = 上限）；网页只读展示。
- 数值变动与检定结果作为机器人消息写入跑团记录。
- `.sc` 附加两条提示（不自动判定疯狂）：一次性损失 ≥5 → 灵感检定由 DM 决定；今日累计损失 vs 不定时疯狂线（当前 SAN 的 1/5）。

## Capabilities

### New Capabilities

- `trpg-vitals`：跑团数值变动与理智检定（指令、边界、权限、规则门控、记录联动、当前值存储）。

### Modified Capabilities

- 无（`coc-character-sheet` 只增加只读展示，不改建卡要求；相关字段在 spec 中作为新增要求写入本能力）。

## Scope and Compatibility

- 不支持一次改多个目标（不做 `@全体`）。
- DND 的临时 HP、死亡豁免、专注不做（留待战斗/先攻功能）。
- 理智检定只报检定结果与阈值提示，**不自动判定**临时/不定时/永久疯狂。
- `.sc` 的损失表达式支持 `数字`、`NdM`、`NdM±K`，骰子数上限 100、面数上限 1000。
- 无数据库变更；旧卡无 `current_*` 字段时按上限初始化，不丢数据。
- 网页不提供改值入口（跨进程写卡无锁，写入收敛到 bot 进程）。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 HP 变动 | `python -m pytest test/test_trpg_vitals.py -q` | `.hp -5` 后卡片 `current_hp` 减 5 且回执含「HP 20 → 15」；扣到负数截断为 0 并提示「HP 归零：昏迷」（DND）/「濒死」（COC）；`.hp 满` 回满；不带符号被拒绝 |
| AC02 骰子表达式 | 同上 | `.hp -1d6` 按掷骰结果扣减，回执带算式明细 |
| AC03 权限 | 同上 | 玩家 @ 他人被拒（「只有 DM」）且对方数值不变；DM @ 他人可改 |
| AC04 规则门控 | 同上 | DND 卡发 `.san` 被拒；本团规则为 COC 而卡片是 DND 时 `.hp` 被拒 |
| AC05 理智检定 | 同上 | D100 ≤ 当前 SAN → 成功扣成功损失；否则失败扣失败损失；成功且损失 0 时数值不变；SAN 归零提示「永久疯狂」；连续两次失败累计「今日累计损失」 |
| AC06 当前值存储 | `python test/scripts/check_trpg_coc_api.py` | 新建 COC 卡 `current_san/current_mp` 缺省等于上限；显式传入 40/6 后原样返回 |
| AC07 记录联动 | 人工/日志 | 录制期间执行指令后，记录 `messages.jsonl` 出现对应机器人消息 |
| AC08 文档与归档 | `python -m pytest -q`；`openspec validate trpg-vitals --strict` | 全量回归绿；菜单/指令表/插件目录同步；`CHANGELOG [1.69.0]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
| AC09 真实环境冒烟 | 部署机手工 | 群里 `.hp -5`、`.san -1`、`.sc 1/1d6` 各一次，回执与网页只读展示一致 |
