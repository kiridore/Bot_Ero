# 实施与验收任务

> 提案 `proposal.md`；设计 `design.md`；规范 `specs/trpg-party-setup/spec.md`（新增）与 `specs/trpg-session-recording/spec.md`（修改）。
> 一次实现覆盖全部条目；每条任务标注对应验收标准，完成后在 `acceptance.md` 记证据。

## 1. 数据层

- [ ] 1.1 新建 `core/trpg/party.py`：`pending_path(group_id)`（复用 `core.trpg.records.group_dir` 的群号校验）、`default_pending(group_id)`、`read_pending(group_id)`（损坏/缺文件返回默认结构 + warning）、`write_pending(group_id, data)`（tmp + `os.replace`）、`set_role(group_id, user_id, role)`、`clear_role(group_id, user_id)`、`set_prepared(group_id, user_id, snapshot)`、`clear_prepared(group_id, user_id)`、`clear_all(group_id)`。对应 AC02、AC03、AC07。
- [ ] 1.2 `core/onebot_client.py`：`_call_onebot` 返回值判定放宽为 dict 或 list；新增 `fetch_group_members(group_id)`（`get_group_member_list`，`no_cache: false`，timeout 5，规范化 `user_id/nickname/is_robot`，失败返回 `None`）。对应 AC04。
- [ ] 1.3 `core/context.py`：移除 `group_roles` 字典与相关读写（改用 `core.trpg.party`）；保留 `recording_sessions[...]["roles"]`。对应 AC02。

## 2. 插件改造

- [ ] 2.1 `plugins/trpg_session/__init__.py` 指令树改为 `/跑团 …`：`match()` 只认裸 `/跑团`、`准备`、`取消准备`、`名单`、`记录 …`；`_route_command` 分发到卡片/准备/记录各子命令；旧 `/跑团记录` 前缀彻底移除。对应 AC01。
- [ ] 2.2 准备与卡片：`/跑团 准备`（取 `character_store.get_current`，无卡回车卡链接；有卡写快照）、`/跑团 取消准备`、`/跑团 名单` 与裸 `/跑团` 输出卡片；卡片含团名、DM、观察者、已准备（昵称 → 角色名/种族/职业/等级）、未准备（@）；准备/取消/`.dm`/`.ob` 后刷新卡片；成员名单不可用时卡片标注并只列已准备者。对应 AC03。
- [ ] 2.3 `.dm` / `.ob`：写 `pending.json`（录制中只写记录 `meta.json`，不重建 pending）；DM 唯一（后设顶掉，设 OB 清 DM，设 DM 清 OB）。对应 AC02。
- [ ] 2.4 开录校验：仅 DM 或超级用户；成员名单获取失败 → 拒绝；DM 缺失/不在群 → 拒绝；普通成员缺角色卡、未准备 → 拒绝；缺失项合并为一条消息；成员数 > 200 → 拒绝并提示强制开始。对应 AC04。
- [ ] 2.5 开录预置：`_start_session` 接收准备名单与角色标记，写 `meta.participants`（DM 首位）与 `meta.roles`，同步会话内存 `participants`/`roles`；成功后删除 `pending.json`。对应 AC06。
- [ ] 2.6 录制中拦截：`准备`/`取消准备`/`名单` 回「录制中无法准备」；`记录 开始` 回「当前已在录制中」；`强制开始` 保持既有语义（丢弃未导出记录）。对应 AC05。
- [ ] 2.7 `plugins/trpg_char/__init__.py`：指令改为 `/跑团 角色 查看|列表|切换|删除`，旧 `/角色` 前缀移除。对应 AC01。
- [ ] 2.8 `plugins/menu/bot_menu_text.py`：删除 `/跑团记录 …` 与 `/角色 …` 全部行，改为新指令树。对应 AC01。

## 3. 网页与文案

- [ ] 3.1 `webapp/static/trpg_records.js`、`trpg_record.js` 与列表/详情页把「群名」文案改为「团名」（字段仍用 `group_name`）。对应 AC08。

## 4. 测试

- [ ] 4.1 更新 `test/test_trpg_session.py`：全部指令前缀改新树；新增 `.dm/.ob` 唯一性与持久化、准备/取消/卡片内容、四类校验失败与合并提示、成员列表失败、成员数超限、`强制开始` 绕过、开录预置与 `pending.json` 清空、录制中拦截、`pending.json` 损坏容错；注入假 `fetch_group_members`。对应 AC01–AC07。
- [ ] 4.2 更新 `test/test_trpg_char.py`：`/跑团 角色 …` 四个子命令；旧 `/角色 …` 不再匹配。对应 AC01。
- [ ] 4.3 确认 `test/scripts/check_trpg_records_api.py` 与 `test/test_trpg_records_dom.js` 仍通过（文案改为「团名」后同步断言）。对应 AC08。

## 5. 文档与交付

- [ ] 5.1 `kb/PLUGIN_CATALOG.md`、`specs/plugin-catalog.md`、`kb/QUICK_REFERENCE.md` 指令表同步；`specs/web-gallery.md` 若涉及「群名」文案一并改为「团名」。对应 AC08。
- [ ] 5.2 `CHANGELOG.md` 新增 `[1.63.0]`（含升级提示：升级前先导出未导出记录），`core/config.py::BOTERO_VERSION` bump 至 1.63.0。对应 AC08。
- [ ] 5.3 全量 `python -m pytest -q` 绿；`openspec validate trpg-party-setup --strict` 与 `openspec validate trpg-session-recording --strict` 通过；逐条 AC 证据写入 `acceptance.md`；`openspec archive 2026-11-10-trpg-party-setup` 与实现同一 commit。真实环境冒烟（AC09）由所有者在部署机执行，结果补记到 `acceptance.md`。
