# 角色昵称持久化 — 验收记录

实施分支：`master`；版本 1.78.1。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 写入昵称 | `test_dm_nickname_saved_in_pending`：`.dm` 后 `roles={"111":"dm"}`、`role_names={"111":"老张"}`；`.ob` 后追加观察者昵称 | 通过 |
| AC02 换 DM 清理 | `test_new_dm_replaces_old_nickname`：换 DM 后 `roles={"222":"dm"}`，`role_names` 只剩新 DM | 通过 |
| AC03 名单显示昵称 | `check_trpg_party_api.py`：`dm_name=守密人`，成员行该用户 `nickname=守密人` | 通过 |
| AC04 前端使用昵称 | `test_trpg_party_render.js`：`DM 守密人` 渲染；缺失 `dm_name` 时回落 `DM 999` | 通过 |
| AC05 文档与归档 | 全量 `pytest` → **768 passed**（4:54）；`openspec validate trpg-preparation --strict` valid；`CHANGELOG [1.78.1]` 与 `BOTERO_VERSION = "1.78.1"` 一致 | 通过 |

## 实测与裁定

- **为什么单独存 `role_names`**：`roles` 的值是角色字符串，改成对象会波及 session、记录 meta、准备名单三处读取；新增一个可缺省字典是零迁移的做法。
- **换 DM 清理**：旧 DM 条目连同昵称一起删除，避免名单里出现「已不是 DM 但还挂着昵称」的脏数据。
- **兼容**：旧 `pending.json` 无 `role_names` → 按空处理，名单回落显示 QQ 号；不升 `PENDING_VERSION`。
- **未做**：录制中 `.dm` 仍只写记录 meta，不重建 `pending.json`（该场景没有准备名单可显示）。
