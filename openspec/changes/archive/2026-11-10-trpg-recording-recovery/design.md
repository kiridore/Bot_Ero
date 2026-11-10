# 设计：录制状态恢复、群解散终止与结束即归档

## 1. 已确认决策

| 编号 | 决策 | 来源 |
|---|---|---|
| D1 | 要修的是「重启后录制停摆」与「记录卡在录制中」；「已结束未导出丢记录」随移除导出消失 | Q1 A+B |
| D2 | 结束录制时自动生成 `record.md`，删除导出指令 | Q2 A |
| D3 | 启动扫描 `end: null` 的目录：7 天内续录，超时写 `end` 标为中断 | Q3 A / Q7 7 天 |
| D4 | 结束录制仅 DM 或超级用户可执行 | Q4 |
| D5 | 结束时不再发合并转发，只回结束信息 + 网页链接 | Q5 |
| D6 | `开始` 不再检查"未导出"；`强制开始` 只表示"跳过准入校验" | Q6 |
| D7 | 运行期不做超时自动结束 | Q8 B |
| D8 | 移除网页「（可能已中断）」提示 | Q9 B |
| D9 | 不为旧记录补生成 `record.md` | Q10 A |
| D10 | 群解散 / 被踢：心跳轮询 `get_group_list` 检测，接口失败不算解散 | Q11 A |
| D11 | 自动终止时 `end` = 最后一条消息时间 | Q12 A |
| D12 | 续录时在记录里写「中断 / 恢复」机器人消息 | Q13 A |
| D13 | 轮流频率 5 分钟 | Q14 B |
| D14 | 续录后在群里发一次恢复公告 | Q15 A |

## 2. 判定算法（启动与运行期共用）

输入：某群某记录目录的 `meta`、`messages`、当前群列表。

```
last_at = 最后一条消息的 time（无消息 → meta.start 的 epoch）
1. 群列表可用且不含该群          → 终止（end = last_at）
2. now - last_at > 7 天          → 终止（end = last_at）
3. 否则                          → 续录
```

- 群列表 `None`（接口不可达）时不执行第 1 条，只按第 2 条判。
- 终止动作：`finalize_record(path, end_ts)` —— 写 `meta.end`、由 `messages.jsonl` 生成 `record.md`；已在录制会话里的群先把会话弹出。

## 3. 启动恢复（`recover_recordings()`）

位置：`plugins/trpg_session/__init__.py` 模块级函数，`main.py` 在 `recover_interrupted_games()` 之后调用。

```python
def recover_recordings() -> int:
    groups = fetch_group_list()          # set[int] | None
    for group_dir in records.records_root().iterdir():   # 群号目录
        for rec_dir in group_dir.iterdir():               # 记录目录
            meta = records.read_meta(rec_dir)
            if not meta or meta.get("version") != 2 or meta.get("end"):
                continue
            if 群已解散 or 超时: finalize_record(rec_dir, last_at); continue
            session = 重建会话(meta, rec_dir)
            append 中断/恢复 消息
            recording_sessions[group_id] = session
            session["resume_banner"] = True   # 等连上 WS 后再发公告
    return 数量
```

- 重建会话字段：`start`（`datetime.strptime(meta["start"])`）、`messages: []`（续录期间只存新消息，供合并转发已删除后不再需要；保留空列表以兼容 `_handle_stop` 排序逻辑）、`participants`（meta.participants 按 user_id 建字典）、`roles`（meta.roles）、`dir`、`img_count`（`imgs/` 现有最大编号）、`resume_banner`。
- 同一群若存在多条 `end: null` 目录（理论上只会有一条），取 `start` 最新的一条续录，其余按超时/异常终止处理（写 `end` = 记录内最后消息时间）。
- 启动时不发群消息：`api.WS_APP` 尚未建立，发送会失败。公告延后到心跳。

## 4. 心跳：5 分钟一次的解散检测与公告

`TrpgSessionPlugin` 改为 `TimedHeartbeatPlugin`，覆写：

```python
_POLL_MINUTES = {0, 5, 10, ...}   # 每 5 分钟
def should_run_on_heartbeat(self, event_type) -> bool:
    if event_type != "meta": return False
    now = datetime.now()
    if now.minute % 5: return False
    key = now.strftime("%Y-%m-%d %H:%M")
    if TimedHeartbeatPlugin._last_run_minute.get("TrpgSessionPlugin") == key: return False
    TimedHeartbeatPlugin._last_run_minute["TrpgSessionPlugin"] = key
    return True

def match(self, message_type):
    return self.should_run_on_heartbeat(message_type) or <原有消息匹配>
```

心跳处理（`handle` 里 `bot_event.message` 为空的分支）：

1. 有 `resume_banner` 的会话 → 发恢复公告，清除标记。
2. `active = list(recording_sessions)`；为空 → 直接返回（不调 `get_group_list`）。
3. `groups = fetch_group_list()`；`None` → 返回。
4. 对 `active` 中不在 `groups` 的群 → `_auto_finish(group_id, "群已解散")`。

## 5. 结束录制

- 权限：`user_id` 是 DM 或登录超管名单内，否则回「只有 DM 才能结束录制」并返回。
- 流程：写 `meta.end` → 生成 `record.md` → 弹会话 → 回「跑团记录已结束——\n查看：<web>/trpg/records/<群号>/<目录>」。
- 不再调用 `_send_forward`；`_send_forward` 方法删除。
- `record.md` 生成失败不再阻断结束（记 `logger.exception`，回执里附「record.md 生成失败」）。

## 6. 网页与状态

- `webapp/trpg/app.py::_record_state`：`meta.end` 为 null → `recording`，否则 → `ended`（不再看 `record.md`）。
- `trpg_records.js` / `trpg_record.js`：`STATE_LABEL = {recording: "录制中", ended: "已结束"}`；删除 `STALE_SECONDS` 与「（可能已中断）」逻辑。
- 旧目录（有 `record.md`）与新目录显示一致：已结束。

## 7. `core/context.py`

- 删除 `last_completed`、`get_last_completed`、`pop_last_completed`。
- `recording_sessions` 保留（运行期状态，启动时由 `recover_recordings()` 重建）。

## 8. `core/onebot_client.py`

新增 `fetch_group_list() -> set[int] | None`：HTTP `get_group_list`，超时 5 秒，`trust_env=False`；返回群号集合，失败返回 `None`。

## 9. 失败路径

| 场景 | 行为 |
|---|---|
| 启动时 `get_group_list` 不可达 | 跳过解散判定，只按 7 天规则；不影响续录 |
| 续录时 `imgs/` 读取失败 | `img_count` 从 0 起（可能覆盖同名文件，记 warning） |
| 生成 `record.md` 失败 | 记日志，记录仍标记为已结束，网页可正常浏览 |
| 同一群多条 `end: null` 目录 | 最新一条续录，其余写 `end` = 各自最后消息时间并生成 md |
| 续录公告发送失败 | 记 warning，保留 `resume_banner`，下个心跳重试（最多到成功一次） |
| 群列表调用失败连续发生 | 不做任何终止，只跳过本轮 |

## 10. 影响面

| 文件 | 改动 |
|---|---|
| `main.py` | 启动调用 `recover_recordings()` |
| `core/context.py` | 删除 `last_completed` 及其 helper |
| `core/onebot_client.py` | 新增 `fetch_group_list` |
| `plugins/trpg_session/__init__.py` | 改继承 `TimedHeartbeatPlugin`；`recover_recordings`；心跳解散检测与公告；结束改自动归档 + 权限；删除导出与合并转发 |
| `plugins/menu/bot_menu_text.py` | 删除 `/跑团 记录 导出` 行 |
| `webapp/trpg/app.py`、`webapp/static/trpg_records.js`、`trpg_record.js` | 两态 + 去掉中断提示 |
| `test/test_trpg_session.py` | 删除导出相关用例，新增恢复/终止/权限/心跳用例 |
| `test/scripts/check_trpg_records_api.py` | 状态断言改两态 |
| `test/test_trpg_records_dom.js` | 标签断言改两态 |
| 文档 | `kb/QUICK_REFERENCE.md`、`kb/PLUGIN_CATALOG.md`、`specs/plugin-catalog.md`、`CHANGELOG.md`、`core/config.py` |

## 11. 测试清单

| 层 | 文件 | 覆盖 |
|---|---|---|
| bot 进程内 | `test/test_trpg_session.py`（扩展） | AC01–AC08 |
| webapp | `test/scripts/check_trpg_records_api.py` | AC09 |
| 前端 DOM | `test/test_trpg_records_dom.js` | AC09 |
| 全量 | `python -m pytest -q` | AC10 |

## 12. 版本

删除用户可见指令 + 行为变更，minor：`BOTERO_VERSION` 1.63.0 → **1.64.0**。
