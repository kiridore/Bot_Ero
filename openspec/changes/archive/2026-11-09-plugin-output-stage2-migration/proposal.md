# 插件消息输出迁移（第二阶段 + 新闻/兑换码）

## Why

`plugin-event-dispatch` 提案留下了分阶段迁移清单：第一阶段（打卡、撤回、抽奖、周常、称号、商店）已完成，第二阶段与第三阶段仍直接调用 `api.send_msg` / `api.call_api`。项目约定“最终所有插件都必须迁移到统一输出模块，不长期保留新旧两套发送方式”。

合并 `community` 线时（1.62.0）明确把 `news`、`who_is_spy`、`redeem_code` 三处列为技术债延后。本次补齐**第二阶段全部 7 个插件**并顺带处理 `news`、`redeem_code`，让第二阶段完整收口，同时验证第三阶段两个简单插件。

现状问题：未迁移的插件绕过统一输出，意味着一部分消息不受“发送位置必须明确、失败不重试、合并与分段统一处理”的约束；`who_is_spy` 还存在直接 `call_api` 的通用发送方法，需要人工审计动作字面量。

## What Changes

- 迁移 9 个插件的聊天消息发送到 `core/message_output.py`：
  - 第二阶段：`who_is_spy`（含 `relay.py` 的 `GameMessenger`）、`activity`、`group_alarm`、`immortal_lottery`、`trpg_session`、`trpg_char`、`trpg_dice`
  - 第三阶段（顺带）：`news`、`redeem_code`
- 发送映射：当前会话回复 → `submit_message`；显式群/私聊 → `submit(..., target=("group"|"private", id))`；合并转发 → `submit(nodes, kind="nodes")`。
- 保留不迁移的调用：撤回 `delete_msg`、下载图片、`get_group_list` 等非聊天消息 API。
- 同步 `migration.md` 清单与 `test_plugin_migration_inventory.py` 的约束（迁移后 `relay.py` 不再有 `call_api`）。

## 行为不变声明

用户可见行为 SHALL 保持不变：消息内容、接收方、顺序、图片与提及结构、失败不重试语义一致。唯一变化是发送时机从插件内立即发送改为同一事件处理结束时统一发送。

## Capabilities

### New Capabilities
无。

### Modified Capabilities
- `plugin-event-processing`：“合并文本与必需输出模块”由“迁移后的消息”扩展为“全部插件的聊天消息”，并补充显式目标与旧入口退役的场景。

## 范围与排除

- 不含第三阶段其余 23 个插件（`dice`、`divination`、`leaderboard`、`menu`、`welcome` 等）。
- 不改变统一输出模块自身的合并/分段/失败语义。
- 不引入新配置项、不新增依赖。
- `plugins/register/__init__.py` 维持既有 Ruling 例外（时序敏感的分段对话需段间停顿），不在本次范围。

## 验收标准

以下测试实现时新增或调整，提案阶段不声称已通过。

| 标准 | 独立执行 | 通过条件 |
|---|---|---|
| AC01 | `python -m pytest test/test_plugin_migration_inventory.py` | 清单覆盖全部发送文件；动态 `call_api` 动作断言不再因 `relay.py` 失败；`migration.md` 已登记 9 个插件的迁移形态 |
| AC02 | `python -m pytest test/test_spy_room_transitions.py test/test_spy_spectating.py test/test_spy_identity_privacy.py test/test_who_is_spy_votes.py` | 卧底全部对局路径通过；群广播、逐玩家私聊、出局观战、合并转发记录结构与迁移前一致 |
| AC03 | `python -m pytest test/test_blacklist_activity_game.py test/test_blacklist_recovery.py` | 黑名单快照仍逐人过滤：被封账号收不到私聊、房间所属群被封时私聊操作静默拒绝 |
| AC04 | `python -m pytest test/test_activity_timer.py test/test_group_review_data.py` | 活动定时事件与群聊/私聊回执通过；私聊提交与群公告目标不变 |
| AC05 | `python -m pytest test/test_scoped_heartbeats.py test/test_timeline_noop.py` | 心跳类插件（闹钟到期、仙人彩开奖）在目标群未启用/被封时不发送，启用时目标正确 |
| AC06 | `python -m pytest test/test_news_subscribe.py test/test_news_weibo.py` | 新闻订阅回执与推送通过；推送目标仍为默认群，`@订阅者` 与图片段结构不变 |
| AC07 | `python -m pytest test/test_redeem_code_stub.py` | 兑换码提示桩：撤回仍执行，提示改为统一输出且 `@` 提及保留 |
| AC08 | `python -m pytest test/test_trpg.py test/test_trpg_char.py test/test_trpg_session.py` | 跑团记录、角色卡、骰点通过；暗骰仍为群内提示 + 私聊结果双目标，不泄露结果到群 |
| AC09 | `python -m pytest` | 全量回归通过 |
| AC10 | `git diff --check` + `openspec validate --all --strict` | 无行尾问题；规范校验通过 |

## 决策记录：`news` 新消息推送（所有者 2026-11-06 选定 A）

`news` 原逻辑在发送失败或未确认时不推进游标、下一轮重推；统一输出在事件末尾集中发送、失败不重试，无法在推进游标前得知结果。

所有者选定 **A**：迁移推送并接受“失败不重试”。游标照常推进，极端情况可能丢一条推送，换取发送路径统一。

对照：`register` 插件因需要分段对话的段间停顿而保留直接发送（既有 Ruling），与此处的取舍不同。

## 提交与发布

内部重构、用户可见行为不变：记 `CHANGELOG.md` `[未发布]` 节，不 bump `BOTERO_VERSION`。若验收中发现任何用户可见行为变化，则改为 patch 版本并补充对应说明。
