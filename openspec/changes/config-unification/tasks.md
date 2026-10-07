# Tasks

## 1. 部署级门控基础

- [ ] 1.1 `core/config.py`：新增 `ALLOWED_PLUGINS` 读取（`bot.allowed_plugins`，空 = None 表示全集）；`core/context.py` 暴露 frozenset 快照（AC01、AC02）
- [ ] 1.2 `core/context.py::plugin_settings_snapshot`：返回值与部署全集相交；`main.py::plugin_pool` 删除 meta 豁免行，全部事件类型统一走 `operation.is_enabled`（AC01）
- [ ] 1.3 启动时校验：SYSTEM_PLUGINS ⊄ ALLOWED_PLUGINS 时 `sys.exit` 报错并列出冲突插件（AC02）
- [ ] 1.4 `test/test_deployment_gating.py`：三级叠加矩阵 + meta 路径 + 私有缺省零变化（AC01、AC02）

## 2. 配置校验服务化

- [ ] 2.1 `core/config.py`：`_REQUIRED_PRIVATE_EXTRA` 分侧删除；timeline/onebot.http 改"非空时成对必填"；`bot.default_group` 移出必填；`_EDITIONS` 白名单移除（edition 任意值可加载，仅日志记录）（AC03）
- [ ] 2.2 冷却默认统一 0；`config.example.yaml` 同步注释；社区模板显式写 3（AC03）
- [ ] 2.3 `test_config_loader.py` 扩展：服务化必填、edition 值无关（同一配置仅改标签全断言一致）（AC03、AC06）

## 3. 功能包数据化

- [ ] 3.1 `core/feature_packs.py`：`bot.feature_packs_file` 加载（yaml 精确替换），缺省回落内置表；单一数据源（AC04）
- [ ] 3.2 `/功能包 列表` 与监控面板核对展示一致；`test_feature_packs_config.py`（AC04）
- [ ] 3.3 `config.example.yaml` 与社区模板的包定义文件示例（AC04）

## 4. 社区配置模板

- [ ] 4.1 `config.example.community.yaml`：allowed_plugins（首版打卡范围）、feature_packs_file、冷却 3、system_plugins 裁剪（无 message_logger/auto_friend/welcome/startup_changelog）（AC06）
- [ ] 4.2 文案包对齐：社区 text_pack 删除经济指令条目，与 allowed_plugins 一致（AC06、AC07）

## 5. 文档与收尾

- [ ] 5.1 `specs/plugins.md` 附录心跳三栏表更新为"受部署门控"；删除"社区白名单"表述（AC07）
- [ ] 5.2 `kb/QUICK_REFERENCE.md`、`specs/conventions.md` 接缝白名单第 4 条改写为"中央门控 = 部署/群/账号三级统一检查"（AC07）
- [ ] 5.3 `docs/community/development-plan.md` T1.2/T0.7 对应条目标注由本提案替代（AC07）
- [ ] 5.4 CHANGELOG + BOTERO_VERSION minor bump（AC05 前置）
- [ ] 5.5 全量 pytest 绿 + `openspec validate config-unification --strict`（AC05、AC08）→ 归档同 commit
