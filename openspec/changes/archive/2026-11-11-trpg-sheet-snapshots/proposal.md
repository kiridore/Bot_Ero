# 跑团记录保存参团角色卡快照

## Why

`meta.json` 的参与者只有 `user_id` / `nickname` / `char_name` / `role`：没有 `char_id`，也没有任何属性、技能、HP/SAN 数值。角色卡升级、改技能、甚至删除之后，记录里只剩一个名字字符串——复盘时无法回答「这场团开始时他是什么水平」「打完这场掉了多少 SAN」。

## What Changes

- 新增 `core/trpg/snapshots.py`：`sheet_snapshot(card)` 按规则压缩出一份卡面（DND：等级/属性/HP/AC/熟练/被动/生命骰/熟练技能；COC：属性/HP/MP/SAN 及上限/MOV/DB/体格/闪避/技能成功率表，最多 80 项，不存笔记与装备长文本）。
- 开录时把 `char_id` 与 `sheet_start` 写进 `meta.participants`；录制中途才发言的玩家，用**首次发言时**的卡作为 `sheet_start`。
- `records.finalize_record()` 写 `end` 时调用 `attach_end_snapshots()` 补 `sheet_end`（角色卡已删除则跳过；快照失败不影响结束流程）。所有结束路径（`/跑团 记录 结束`、群解散、7 天超时）都经过这里。
- 网页记录详情新增可折叠「参团角色卡（开始 / 结束）」区块，显示起止数值与本场变化（等级、HP 上限、SAN、当前 HP）。

## Capabilities

### Modified Capabilities

- `trpg-session-recording`：记录参与者存角色卡快照。

## Scope and Compatibility

- 只影响新记录；旧记录没有 `sheet_start` / `sheet_end`，页面不显示该区块。
- 快照是有损压缩：不含笔记、装备清单、特性长文本、成长标记等，避免 `meta.json` 膨胀。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 快照内容 | `python -m pytest test/test_trpg_snapshots.py -q` | DND 快照含 level/hp/ac/prof_bonus/熟练技能；COC 快照含 current_san/san/技能成功率；`notes`/`equipment` 不进快照 |
| AC02 结束补写 | 同上 | 有 `char_id` 的参与者补上 `sheet_end`；角色卡已删除则跳过且不抛错；无 `char_id` 不查库 |
| AC03 开录写入 | `python -m pytest test/test_trpg_session.py -q -k SheetSnapshots` | 开录后 `participants[0]` 含 `char_id` 与 `sheet_start`；结束并升级卡后 `sheet_end.level` 与起始不同；删卡后仍有 `sheet_start`、缺 `sheet_end` |
| AC04 页面 | 人工看记录详情 | 折叠区块显示「开始 / 结束」两行；本场有变化时显示「本场变化：Lv 3→4…」；旧记录不显示区块 |
| AC05 文档与归档 | `python -m pytest -q`；`openspec validate trpg-session-recording --strict` | 全量回归绿；`CHANGELOG [1.74.0]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
