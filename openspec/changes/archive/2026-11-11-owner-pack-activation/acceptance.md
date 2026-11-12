# 群主自助开启功能包 — 验收记录

实施分支：`master`；版本 1.75.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 跑团包完整 | `test_group_manager_owner.py::test_pack_includes_vitals`：`FEATURE_PACKS["跑团"]` 含四个插件 | 通过 |
| AC02 群主开包 | `/功能包 跑团` → 「已开启功能包「跑团」…」且 `group_plugin_config` 写入四行；`/功能包 基础包` 写入 `checkin` 等 | 通过 |
| AC03 群主边界 | 白名单外的「休闲娱乐」被拒且配置为空；`off` 被拒且原配置保留；`/功能包 跑团 987654` 被拒；`/插件 trpg_dice` 被拒 | 通过 |
| AC04 权限分离 | `role=admin` 被拒（「仅超级用户」）；超级用户可开启「休闲娱乐」 | 通过 |
| AC05 文档与归档 | 全量 `pytest` → **743 passed**（4:45）；`openspec validate plugin-management --strict` valid；菜单与 QUICK_REFERENCE 已同步；`CHANGELOG [1.75.0]` 与 `BOTERO_VERSION = "1.75.0"` 一致 | 通过 |

## 实测与裁定

- **取消 `/跑团 初始化`**：所有者裁定改用现有 `/功能包` 开权限，不再新增一键关闭指令。
- **权限模型**：`owner_user()` 只认 `sender.role == "owner"` 与超级用户；群管理员（`admin`）不算。
- **越权路径全部堵死**：`_owner_request()` 在写入前依次校验「群聊」「指令是 /功能包」「目标群是本群」「包存在」「动作是开启」「包在白名单」，任一不满足即返回对应文案且不写库。
- **未做**：新群自动播种（所有者选择不做，群主主动开一次）；数据库不记录「谁开的包」。
