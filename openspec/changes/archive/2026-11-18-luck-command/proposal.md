# `.幸运` 指令：团内增减幸运

## Why

COC 7th 的幸运在团里会被频繁消耗（花幸运点改判、KP 奖励、模组效果），现在只能回网页改卡。这一轮只做幸运一项（其它属性改动会连带 HP/MP/MOV/预算与年龄调整记录，另议）。

## What Changes

- 新增 `.幸运 <±值> [@目标]` 与英文别名 `.luck`：
  - 数值形态与 `.hp` 一致：`-10`、`+5`、`-1d6`（复用 `roll_expression`，负合计已夹到 0）。
  - 截断在 0–99：花超只到 0 并提示「幸运已见底（不会低于 0）」，加超只到 99 并提示「多出的部分不计」。
  - 本人可改自己；`@他人` 需本群 DM 或超级用户（与 `.hp`/`.sc` 一致）。
  - 非 COC 角色卡拒绝：「幸运是 COC 7th 的数值，当前角色卡是 DND 5E」。
  - 回执写入跑团记录（`record_bot_message`）。
- 菜单与 `kb/DICE_GUIDE.md` 同步。

## Capabilities

### Modified Capabilities

- `trpg-vitals`：新增幸运增减指令。

## Scope and Compatibility

- 只动幸运字段 `luck`，不碰其它属性、不触发派生值重算（幸运没有派生）。
- 幸运不是年龄调整的一部分（15–19 的「幸运掷两次取高」在建卡页），因此与 `age_adjust` 无交互。
- 版本 2.2.0。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 减少 | `python -m pytest test/test_trpg_vitals.py -q -k TestLuck` | `.幸运 -10`：45 → 35，回执 `幸运 45 → 35（-10）` |
| AC02 增加 | 同上 | `.幸运 +5`：45 → 50 |
| AC03 英文别名 | 同上 | `.luck -5`：45 → 40 |
| AC04 骰子 | 同上 | `.幸运 -1d6`（掷 3）：45 → 42，明细 `-d6=3` |
| AC05 下限 | 同上 | `.幸运 -50`：5 → 0 且提示「见底」 |
| AC06 上限 | 同上 | `.幸运 +50`：90 → 99 且提示「上限 99」 |
| AC07 格式 | 同上 | 无正负号与缺参数各给出提示，卡不变 |
| AC08 规则门控 | 同上 | DND 卡提示「COC 7th」 |
| AC09 权限 | 同上 | 玩家 `@` 他人被拒；DM 可 `@` |
| AC10 全量回归 | `python -m pytest -q` | 全绿 |
| AC11 文档与归档 | `openspec validate trpg-vitals --strict`；归档与实现同一 commit | 菜单与 `kb/DICE_GUIDE.md` 含 `.幸运`；`CHANGELOG [2.2.0]` 与 `BOTERO_VERSION` 一致 |
