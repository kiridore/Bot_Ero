# 修复编辑角色卡把当前 HP/MP/SAN 清零

## Why

所有者反馈：车完一张 COC 卡保存后，查看页显示 `HP 0/9 · MP 0/13 · SAN 0/99`。

根因在编辑接口：`CharacterIn` 的 `current_hp/current_mp/current_san` 默认值是 `0`，而建卡页保存时不带这三个字段。于是：

- **新建**时 `if not data.get(key)` 为真，会把 0 当作「没填」按上限初始化 —— 这一步侥幸正确；
- **编辑**（PUT）没有任何补偿，`model_dump()` 里的 0 直接覆盖卡上的真实值 → 存成 0，之后 `finalize` 的 `_clamp_or(0, …)` 也返回 0，永远回不去。

同时发现 COC 没有 `.mp` 指令，卡上 MP 被清零后无法在群内恢复。

## What Changes

- `CharacterIn` 的 `current_hp/current_mp/current_san` 改为 `int | None = None`（`None` = 未提供，`0` 是合法值）。
- 新建：`_fill_current_values()` 在值为 `None` 时按上限初始化（两套规则都适用）。
- 编辑：`_keep_current_values()` 在值为 `None` 时沿用卡上原值；显式传 `0` 仍按 0 保存（濒死/昏迷是合法状态）。
- 新增 `.mp <±值|满> [@目标]` 指令（COC 专属，与 `.san` 同构），补齐 MP 的恢复手段。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：当前值的保存语义。
- `trpg-vitals`：新增 `.mp`。

## Scope and Compatibility

- 已存成 0 的卡需要群内执行一次 `.hp 满` / `.san 满` / `.mp 满` 恢复（`0` 与「未设置」在存储上无法区分，不做自动迁移以免误改真正的濒死状态）。
- 网页仍然只读当前值（1.69 的跨进程写入约定不变）。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 新建初始化 | `python test/scripts/check_trpg_coc_api.py` | 新建后 `current_hp=10`、`current_mp=13`、`current_san=65` |
| AC02 编辑不清零 | 同上 | 不带 `current_*` 的 PUT 后三项仍等于新建时的值 |
| AC03 显式 0 保留 | 同上 | `current_hp=0` 的 PUT 后仍是 0 |
| AC04 `.mp` | `python -m pytest test/test_trpg_vitals.py -q -k Mp` | `.mp -3` → `MP 13 → 10`；`.mp 满` 回满；DND 卡被拒绝 |
| AC05 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿；`CHANGELOG [1.82.1]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
