# 录制暂停 — 验收记录

实施分支：`master`；版本 1.87.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 暂停 | `TestPause::test_pause_marks_session_and_meta`：会话 `paused=True`、`meta.paused=True`、`paused_at` 为 int、记录里有「暂停」 | 通过 |
| AC02 权限 | `test_pause_requires_dm`（非 DM 拒绝）、`test_pause_without_recording`（无录制提示）、`test_pause_twice`（已暂停提示） | 通过 |
| AC03 不入档 | `test_messages_not_recorded_while_paused`：暂停期间用户发言与 `.r` 回复都不写 jsonl | 通过 |
| AC04 续录 | `test_resume_skips_gate`：准备名单已空仍可续录，写入「恢复」；`test_start_while_recording` 提示已在录制中 | 通过 |
| AC05 恢复后照常 | `test_resume_then_records_again`：续录后新消息 +1 | 通过 |
| AC06 结束清理 | `test_stop_clears_pause`：`paused=False` 且 `end` 已写 | 通过 |
| AC07 重启 | `test_restart_keeps_paused`：恢复后仍暂停、无「中断」消息 | 通过 |
| AC08 群公告 | `test_paused_banner_text`：公告含「暂停状态」与 `/跑团 记录 开始` | 通过 |
| AC09 网页状态 | `check_trpg_records_api.py`：列表与详情 `state == "paused"`、`end is None`；详情 DOM：徽标「已暂停」；列表 DOM：徽标与时间行「已暂停」 | 通过 |
| AC10 全量回归 | `python -m pytest -q` → **918 passed**（5:11） | 通过 |
| AC11 文档与归档 | `openspec validate trpg-session-recording --strict` valid；`bot_menu_text.py` 与 `kb/QUICK_REFERENCE.md` 已加指令；`CHANGELOG [1.87.0]` 与 `BOTERO_VERSION = "1.87.0"` 一致 | 通过 |

## 实测回放（本地临时配置）

```
user | 开团第一句
bot  | 录制于 12:57 暂停
（暂停期间的聊天与 .r 结果都不在记录里）
bot  | 录制于 12:57 恢复
user | 继续
meta paused: False
```

## 裁定

- **静默模式保留**：暂停期间群仍处于录制静默模式（只有 4 个跑团插件响应），暂停只关闭「入档」，不关闭会话。这样续录不需要重建会话，也不会让其它插件在团中途插话。
- **暂停标记先入档再切换状态**：`record_bot_message` 在暂停后会被跳过，所以「录制于 HH:MM 暂停」必须在切换前写。
- **续录权限**：`/跑团 记录 开始` 仍要求 DM（与非暂停态一致），只是跳过准入校验；`强制开始` 语义不变。
- **7 天规则照旧**：暂停记录的最后一条消息是暂停标记，超过 7 天重启会被归档。
- **未做**：暂停时长不计入总时长（`durationText` 仍按开始-结束算）；暂停期间的消息不补录（拿不到）。
