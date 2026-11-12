# 准备卡片剔除机器人 — 验收记录

实施分支：`master`；版本 1.77.3。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 卡片剔除机器人 | `test_card_excludes_bot_from_pending`：成员含 DM、一个未准备玩家、机器人自己、另一个机器人 → 输出「已准备 0/1」，不含两个机器人 QQ | 通过 |
| AC02 守卫有效性 | 把 `_human_members` 临时改回 `return members` 后重跑：用例失败并打印实际输出「已准备 0/3 … 未准备：@3915014383 @999 @222」；恢复后通过 | 通过（已验证能捕获） |
| AC03 校验口径不变 | `test_trpg_session.py` 83 例全过 | 通过 |
| AC04 文档与归档 | 全量 `pytest` → **764 passed**（4:41）；`openspec validate trpg-preparation --strict` valid；`CHANGELOG [1.77.3]` 与 `BOTERO_VERSION = "1.77.3"` 一致 | 通过 |

## 根因与裁定

- **根因**：成员过滤写在 `_check_gate` 里，`_card_segments` 另走一条路径没过滤；同一口径写两遍必然跑偏。
- **统一**：抽出 `_human_members(group_id)`（剔除 `is_robot` 与 `BOT_QQ`，接口失败返回 `None`），卡片与开录校验都走它；`_check_gate` 里原先的重复过滤删除。
- **降级不变**：接口失败时卡片仍显示「（成员名单不可用，未准备者未知）」，开录仍拒绝并提示可强制开始。
