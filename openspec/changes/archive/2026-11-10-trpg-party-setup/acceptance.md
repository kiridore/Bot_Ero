# 跑团开团前准备与准入校验 — 验收记录

实施分支：`master`；版本 1.63.0；提案 `openspec/changes/2026-11-10-trpg-party-setup/`。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 指令迁移 | `python -m pytest test/test_trpg_session.py test/test_trpg_char.py -q` → 85 passed（含 `test_old_command_not_matched`、`test_role_subcommand_left_to_char_plugin`、`test_old_command_no_longer_matches`、`test_other_party_subcommand_not_matched`）；`grep -c "^/跑团记录\|^/角色" plugins/menu/bot_menu_text.py` → 0 | 通过 |
| AC02 角色标记 | 同专项：`.dm` 写入 `pending.json` 且卡片显示 DM；第二人 `.dm` 顶掉旧 DM（`roles == {"222": "dm"}`）；同一人 `.ob` 后不再为 DM | 通过 |
| AC03 准备流程 | 同专项：无卡 `准备` 被拒且名单为空；有卡准备后名单记录角色名/等级且卡片显示；准备后切换当前角色卡，快照不变；`取消准备` 移除条目；录制中准备被拒 | 通过 |
| AC04 准入校验 | 同专项（注入假 `fetch_group_members`）：无 DM 被拒；成员缺卡 + 成员未准备**合并为一条消息**且 @ 出两人；DM 与观察者无卡未准备仍通过；成员列表 `None` 被拒并提示；成员 202 人被拒并提示超限；机器人成员被排除 | 通过 |
| AC05 强制开始 | 同专项：无 DM、成员缺卡时 `/跑团 记录 强制开始` 仍创建记录；存在未导出记录时提示「已丢弃」并清空 | 通过 |
| AC06 开录预置 | `test_participants_preseeded_and_pending_cleared`：开录后 `meta.participants` 为 `["111","222"]`（DM 首位）、`roles == {"111":"dm"}`、玩家条目带角色卡名 `阿铁`；`pending.json` 已删除；录制中 `/跑团 准备` 被拒 | 通过 |
| AC07 持久化 | 准备名单经 `party.write_pending`（tmp + `os.replace`）；`test_pending_file_corrupt_is_tolerated` 写入非法 JSON 后 `/跑团` 仍正常响应；新建插件实例读取同一文件仍能看到准备与标记（跨实例持久化） | 通过 |
| AC08 网页与文档 | `python -m pytest -q` → **556 passed**（4:07）；`python test/scripts/check_trpg_records_api.py` 全过；`node test/test_trpg_records_dom.js` 全过（文案已改「团名」）；`openspec validate trpg-party-setup --strict` 与 `trpg-session-recording --strict` 均 valid；`CHANGELOG.md` 顶部 `[1.63.0]` 与 `BOTERO_VERSION = "1.63.0"` 一致；`kb/QUICK_REFERENCE.md`、`kb/PLUGIN_CATALOG.md`、`specs/plugin-catalog.md` 指令表已更新 | 通过 |
| AC09 真实环境冒烟 | 待所有者在部署机执行：`.dm` → 玩家 `/跑团 准备` → `/跑团` 卡片 → DM `/跑团 记录 开始` → 网页 `/trpg/records` 看到该团 | 未执行（需真实 QQ 环境） |

## 实测与裁定

- **`get_group_member_list` 上游确认**：实施前查了 LLOneBot 文档单页（`https://api.luckylillia.com/api-120763084.md`），返回 `data` 为数组，字段含 `user_id` / `nickname` / `card` / `card_or_nickname` / `is_robot`，与实现一致。
- **`_call_onebot` 放宽返回值**：原来只接受 dict 的 `data`，群成员列表是数组会被吞成 `{}`；改为接受 dict 或 list。昵称/头像/群名这些走 dict 的调用方行为不变。
- **强制开始不再撞接口**：`/跑团 记录 强制开始` 是"成员接口坏了"的逃生通道，实施后改为不再调用 `fetch_group_members`，否则会先等 5 秒超时两次才开录。
- **测试隔离补齐**：`core.character_store.CHARS_ROOT` 是独立于 `PYTHON_DATA_PATH` 的配置，之前测试未隔离，先跑的用例会把角色卡漏给后跑的用例；`use_temp_data_path()` 一并 patch 它。
- **`core/context.py::group_roles` 移除**：角色标记改存 `pending.json`，避免内存与文件两套状态。录制期间 `.dm`/`.ob` 只写记录 `meta.json`，不重建 `pending.json`。
- **机器人消息入档保留**：录制中 `.dm`/`.ob` 的提示语仍以 `sender_type: "bot"` 入档（1.62.0 行为不变）。
- **未验证**：没有真实 QQ 环境跑过；`get_group_member_list` 的真实返回未在本机验证（本机无 OneBot），字段结构按上游文档实现。
