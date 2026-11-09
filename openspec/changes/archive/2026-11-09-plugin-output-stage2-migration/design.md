# 设计：插件消息输出迁移（第二阶段 + 新闻/兑换码）

## 1. 统一输出契约（已存在，不修改）

- `MessageOutput.submit(content, *, target=None, kind="text", merge=None, order=0, node=None)`
  - `target` 必须是 `("group", 正整数)` 或 `("private", 正整数)`；`None` 用事件默认位置（`main.py`：群 → 私聊 → 默认群）。
  - `kind`：`text`（字符串，可合并）、`segments`（消息段列表）、`forward`/`nodes`（合并转发）、`forward_text`（按 `node` 序号聚合的转发文本）。
- 框架在事件处理结束后统一 `operation.finish()`（drain + flush），插件只提交不发送。
- 失败不重试、只记日志；已提交的业务不因发送失败回滚。
- `send_request` 最终调用 `ApiWrapper.send_msg`，称号前缀注入与 @ 处理保持不变。

## 2. 通用映射规则

| 当前写法 | 迁移后 | 说明 |
|---|---|---|
| `self.api.send_msg(text(x))` | `self.submit_message(text(x))` | 发当前会话；全文本自动降为 `kind="text"` |
| `self.api.send_msg(at(u), text(x))` | `self.submit_message(at(u), text(x))` | 含非文本段 → `kind="segments"`，@ 保留 |
| `self.api.send_msg(*segs)`（当前会话） | `self.submit_message(*segs)` | 同上 |
| `api.call_api("send_group_msg", {"group_id": g, "message": segs})` | `output.submit(segs, target=("group", g), kind="segments")` | 目标显式 |
| `api.call_api("send_private_msg", {"user_id": u, "message": segs})` | `output.submit(segs, target=("private", u), kind="segments")` | 目标显式 |
| `api.send_forward_nodes(nodes)`（当前会话） | `self.operation.output.submit(nodes, kind="nodes")` | 当前会话目标 |
| `api.call_api("send_group_forward_msg", {...})` | `output.submit(nodes, kind="nodes", target=("group", g))` | 目标显式 |
| `api.delete_msg(id)` | **保持不变** | 撤回不是发送 |
| `api.call_api("get_group_list" / 下载)` | **保持不变** | 非聊天消息 |

各插件拿到 `output` 的两种途径：`CommandPlugin`/`Plugin` 子类用 `self.submit_message(...)`（内部即 `self.operation.output.submit`）；模块级函数或非插件类（如 `GameMessenger`）由调用方传入 `operation.output`。

## 3. 逐插件处理要点

### 3.1 `who_is_spy`（最难）

- `relay.GameMessenger` 由“持有 `api` 并立即 `call_api`”改为“持有 `output`”：
  - `private(room, uid, body)` → `output.submit([text(body)], target=("private", int(uid)), kind="segments")`
  - `group(room, body)` → `output.submit([text(body)], target=("group", int(room['group_id'])), kind="segments")`
  - 群转发 → `output.submit(nodes, kind="nodes", target=("group", int(room['group_id'])))`
  - 删除 `send(action, params)` 的 if/elif 分支与 `call_api` 调用。
- **必须保留**的三项判断，位置不变（在 `submit` 之前）：
  1. 黑名单快照：`isinstance(snapshot, BlacklistSnapshot) and snapshot.blocks(user_id=int(uid))` → 跳过。
  2. 已退出者：`store.can_receive(record_id, uid)` 失败/否 → 跳过。
  3. 出局者静默：`room['players'][uid].get('left')` → 跳过。
- 逐玩家私聊是不同 `target`，不会被合并；群内多条无标记消息保持独立（`merge=None` 时每批次单独发送）。
- `_reply(body, forward=False)`：普通 → `submit_message(text(body))`；转发 → `submit_message(nodes, kind="nodes")`。
- 发送时机从“结算后立即发”变为“事件末尾统一发”，语义等价。

### 3.2 `news`

- 9 处订阅/退订回执 → `submit_message(text(...))`。
- 推送 `self.api.send_msg(*segs)` → `self.operation.output.submit(segs, target=("group", DEFAULT_GROUP_ID), kind="segments")`。
  - 目标在既有门控中已读取 `DEFAULT_GROUP_ID` 且非空才继续，因此显式传值安全。
- `@订阅者` 与图片段结构不变（`segs` 原样传入）。

### 3.3 `redeem_code`

- `send_msg(at(user), text(TIP))` → `submit_message(at(user), text(TIP))`；无 `user_id` 分支 → `submit_message(text(TIP))`。
- `delete_msg` 保留。

### 3.4 `activity`

- 模块级 `_send_private(api, uid, *msg)` / `_send_group(api, gid, body)`（当前用 `call_api`）改为接收 `output` 的两个辅助函数，内部 `output.submit(...)`。
- 所有指令回执 → `submit_message(text(...))`。
- 定时事件（`ActivityTimerPlugin`）目标为活动所属群，显式 `target=("group", gid)`。
- 保留“活动进行中不向他人外发提交内容”的既有隐私判断。

### 3.5 `group_alarm`

- 指令回执 → `submit_message`。
- 到期通知当前用 `call_api` 私聊/群发送，改为按闹钟记录的目标显式 `submit`。

### 3.6 `immortal_lottery`

- 下注与查询回执 → `submit_message`。
- 开奖 `call_api("send_group_msg", ...)` → `output.submit(..., target=("group", gid), kind="segments")`。

### 3.7 `trpg_session`

- 指令回执 → `submit_message`。
- `_send_forward(group_id, messages)` 改为 `output.submit(nodes, kind="nodes", target=("group", gid))`。

### 3.8 `trpg_char`

- 全部为当前会话文本回执 → `submit_message(text(...))`。

### 3.9 `trpg_dice`

- 明骰 → `submit_message(text(out))`。
- **暗骰**（群内提示 + 私聊结果）双目标：
  - `self.submit_message(text("悄悄掷出骰子"))`（当前群）
  - `self.operation.output.submit([text(full)], target=("private", uid), kind="segments")`
- 保留“私聊不泄露结果到群”的既有约束。

## 4. 风险与对策

| 风险 | 对策 |
|---|---|
| 发送时机变化导致测试断言“立即发送”失败 | 逐个检查相关测试，改为断言输出请求而非 `api.send_msg` 调用 |
| `Mock` 的 `api` 属性自返回真值，误判 | 与合并时相同的教训：对 `blacklist_snapshot` 做 `isinstance` 判断 |
| 心跳类插件默认目标被误用为当前事件位置 | 显式传 `target`，不依赖默认值 |
| 私聊/群聊лемент混发导致内容串台 | 统一输出按 `target` 分组；测试覆盖“同标记不同目的地” |
| 迁移后 `test_plugin_migration_inventory` 的清单与断言失配 | 同步更新 `migration.md`，迁移条目改为“已迁移” |
| 大量 `submit` 造成 `send_request` 反复建 `ApiWrapper` | 既有设计，本次不改；实测卧底一局约 10 人私聊，可接受 |

## 5. 测试策略

- 既有行为测试优先：先跑各插件现有测试，确认迁移后全绿；失败即说明行为变化，需判断是实现错误还是测试断言需同步。
- 新增断言：迁移插件在正常路径下 `api.send_msg` 不再被调用（改为校验输出请求），防止“看似迁移、实际仍直发”。
- 心跳/定时类：保持既有的门控测试（未启用/被封不发送）。
- 清单测试：`test_plugin_migration_inventory.py` 是硬约束，迁移后 `relay.py` 不再有 `call_api`。

## 6. 执行顺序

按风险从低到高，便于早期发现问题：

1. 简单文本插件：`trpg_char` → `trpg_dice`（含暗骰双目标）
2. 回执为主：`redeem_code` → `group_alarm` → `immortal_lottery`
3. 含转发/定时：`trpg_session` → `activity`
4. 推送与目标显式：`news`
5. 最复杂：`who_is_spy`（`relay.py` + `__init__.py`）
6. 收尾：`migration.md`、清单测试、CHANGELOG、全量回归

每完成 1–2 个插件跑其定向测试，全部完成后跑全量。
