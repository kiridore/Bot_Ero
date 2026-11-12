# DM 昵称实时查询 — 验收记录

实施分支：`master`；版本 1.79.5。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 实时优先 | `check_trpg_party_api.py`「DM 昵称实时获取」：桩返回「实时名片」时接口 `dm_name == "实时名片"` | 通过 |
| AC02 回落快照 | 同脚本「实时取不到回落快照」「DM 昵称回落快照」：桩返回空串时得到「守密人」 | 通过 |
| AC03 缓存策略 | `TestMemberNameCache`：成功/失败各只请求一次（`call_count == 1`）；`use_cache=False` 时请求两次；非法 ID 返回空串 | 通过 |
| AC04 名片优先昵称 | `test_card_empty_falls_back_to_nickname`：`{"card":"","nickname":"昵称"}` → 「昵称」 | 通过 |
| AC05 文档与归档 | 全量 `pytest` → **790 passed**（4:57）；`openspec validate trpg-party-roster --strict` valid；`CHANGELOG [1.79.5]` 与 `BOTERO_VERSION = "1.79.5"` 一致 | 通过 |

## 实测与裁定

- **为什么改用 A**：`group_card` 通知的可用性无法在本机验证（`specs/llms.txt` 只有设置名片的 API）。webapp 现拉不依赖任何推送行为，`onebot.http_url` 配好即可用——同一通道早就在给论坛/活动/时间线解析昵称。
- **超时与缓存**：`get_group_member_info` 超时从 3 秒降到 2 秒；成功缓存 60 秒、失败缓存 30 秒。最坏情况（OneBot 挂）每 30 秒才付一次 2 秒代价，其余请求零延迟。
- **两条路径并存**：`group_card` 仍然写 `pending.json`（`use_cache=False`，拿最新值），保证不进网页也能有较新的快照；网页则以实时查询为准。
- **未做**：名单里其他成员（玩家/观察者）仍用 `/跑团 准备` 时的昵称快照——它们本来就随准备动作刷新，且不为每行多发一次 HTTP。
