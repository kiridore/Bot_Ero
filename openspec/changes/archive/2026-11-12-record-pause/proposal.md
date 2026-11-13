# 录制暂停：`/跑团 记录 暂停`

## Why

跑团中途常常要休息（吃饭、换人、中途讨论规则），但录制一旦开始就一直在收，休息期间的闲聊全部进记录。目前只能「结束录制」，而结束之后要重开就得重新走一遍准备流程。

## What Changes

- 新增 `/跑团 记录 暂停`（DM 或超级用户）：把录制切到暂停态，期间的**用户消息与机器人回复都不入档**，但会话仍在（群仍处于录制静默模式，`.r`/`.hp` 等跑团指令照常响应，只是不写记录）。
- 暂停态下 `/跑团 记录 开始` 直接续录，**不校验准备状态**（准备名单在开录时已清空，重新校验必然失败）。`/跑团 记录 强制开始` 行为不变。
- 暂停/恢复各写一条机器人记录：「录制于 HH:MM 暂停」「录制于 HH:MM 恢复（暂停 N 分钟）」。
- `meta.json` 新增 `paused` 与 `paused_at`；网页状态从两态变三态（录制中 / 已暂停 / 已结束），列表与详情都显示「已暂停」，详情页在暂停态下继续轮询，恢复后徽标自动变回「录制中」。
- 重启恢复：暂停中的记录重启后仍是暂停态，不写「中断/恢复」消息，群公告改为「录制处于暂停状态，发送 /跑团 记录 开始 可继续」。
- 结束录制时清掉暂停标记。

## Capabilities

### Modified Capabilities

- `trpg-session-recording`：暂停/续录的语义、入档开关、重启恢复与结束清理。
- `trpg-record-web`：三态徽标与暂停态轮询。

## Scope and Compatibility

- 不影响既有录制流程；未暂停时行为与之前完全一致。
- 暂停期间的对话不补录（与重启断档同理，物理上拿不到）。
- 暂停记录仍受「最后一条消息超过 7 天自动归档」约束。
- 无数据库变更、无新增依赖；版本 1.87.0。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 暂停 | `python -m pytest test/test_trpg_session.py -q -k Pause` | DM 发送 `/跑团 记录 暂停` 后会话 `paused=True`、`meta.paused=True`、`paused_at` 为整数，记录里有「暂停」机器人消息 |
| AC02 权限 | 同上 | 非 DM 被拒（「只有 DM 才能暂停录制」）；无录制时提示「当前没有进行中的记录」；重复暂停提示已暂停 |
| AC03 不入档 | 同上 | 暂停期间用户发言与 `.r` 的机器人回复都不写 `messages.jsonl` |
| AC04 续录 | 同上 | 暂停后 `/跑团 记录 开始` 直接续录（准备名单已空也不拦），写入「恢复」消息；再次发送提示「当前已在录制中」 |
| AC05 恢复后照常 | 同上 | 续录后新消息继续入档 |
| AC06 结束清理 | 同上 | 暂停中 `/跑团 记录 结束` 后 `meta.paused` 为 False 且 `end` 已写 |
| AC07 重启 | 同上 | 暂停记录 `recover_recordings()` 后仍是暂停态，且没有「中断」消息 |
| AC08 群公告 | 同上 | 暂停态的恢复公告文案为「暂停状态 … /跑团 记录 开始」 |
| AC09 网页状态 | `python test/scripts/check_trpg_records_api.py`；`node test/test_trpg_records_dom.js`；`node test/test_trpg_records_list_dom.js` | 列表/详情 `state == "paused"`；详情徽标「已暂停」；列表徽标与时间行显示「已暂停」 |
| AC10 全量回归 | `python -m pytest -q` | 全绿 |
| AC11 文档与归档 | `openspec validate trpg-session-recording --strict`；归档与实现同一 commit | `CHANGELOG [1.87.0]` 与 `BOTERO_VERSION` 一致；`bot_menu_text.py` 与 `kb/QUICK_REFERENCE.md` 已加指令 |
