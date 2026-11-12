# 修复准备卡片把机器人算进未准备名单

## Why

群内 `.dm` 或 `/跑团` 触发的准备卡片，在统计「未准备」时直接用了 `get_group_member_list` 的原始结果，没有剔除机器人。于是机器人自己（以及群里其它机器人）被当成待准备的玩家：分母虚高（`已准备 0/3`）、`未准备：@机器人 @…` 里出现 bot 自己的 QQ。

开录校验 `_check_gate` 里其实过滤过一次（`not is_robot and user_id != BOT_QQ`），两处逻辑各写一遍，导致只修了一处。

## What Changes

- `plugins/trpg_session/__init__.py` 新增 `_human_members(group_id)`：取成员名单并剔除 `is_robot` 与机器人自己；接口不可用时返回 `None`（与原语义一致）。
- 准备卡片 `_card_segments` 与开录校验 `_check_gate` 都改用该方法，口径统一在一处。

## Capabilities

### Modified Capabilities

- `trpg-preparation`：准备卡片与开录校验的成员口径。

## Scope and Compatibility

- 只是把已有的过滤逻辑提取并补齐到卡片路径，不改任何用户可操作流程与数据结构。
- 成员接口失败的降级行为不变：卡片显示「（成员名单不可用，未准备者未知）」，开录仍拒绝。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 卡片剔除机器人 | `python -m pytest test/test_trpg_session.py -q -k card_excludes_bot` | 群里含机器人自己与另一个机器人时，「已准备 0/1」且输出不含这两个 QQ |
| AC02 回归守卫有效性 | 把 `_human_members` 改回直接返回原名单后重跑同一用例 | 用例失败（`已准备 0/3`，并 @ 了机器人） |
| AC03 校验口径不变 | `python -m pytest test/test_trpg_session.py -q` | 全部通过（含开录校验既有用例） |
| AC04 文档与归档 | `python -m pytest -q`；`openspec validate trpg-preparation --strict` | 全量回归绿；`CHANGELOG [1.77.3]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
