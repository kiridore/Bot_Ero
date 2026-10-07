# 配置统一化 · 设计

## 核心思路

三级开关模型（自上而下截断）：

```
部署级 allowed_plugins（进程内，config）
  └─ 群开关 group_plugin_config（库）
      └─ 账号覆盖 plugin_settings 三态（库）
```

任何一级关闭即关闭。`plugin_settings_snapshot(group_id, user_id)` 的返回值在原有两级之上先与部署全集相交；meta 事件（无群无账号上下文）的快照 = 部署全集 ∩ 系统插件集。检查函数只有这一个入口，消息/通知/请求/notice/meta 全部经它——消除"meta 旁路"。

## 关键设计决策

### D1：allowed_plugins 是"部署能力声明"，不是第四套开关表

- config 键 `bot.allowed_plugins: []`，空/缺省 = 全部已注册插件（私有兼容，零变化）
- 不落库、不可通过群指令修改——它回答"这个部署装了什么"，群/账号开关回答"谁在哪里用"
- 与 system_plugins 的关系：系统插件 = 免群开关检查（现有语义保留）；allowed_plugins = 部署硬边界。系统插件 ∉ allowed_plugins 时启动即报错（防止"偷偷启用"，config-only 核查规则 5）

### D2：meta 收口的粒度

- `plugin_pool` 对 meta 事件：快照 = `allowed_plugins ∩ (SYSTEM_PLUGINS ∪ 有心跳行为的插件)`
  - 简化实现：不做"有心跳行为的插件"特判，直接用 allowed_plugins ∩ SYSTEM_PLUGINS 再并上 allowed_plugins 内其余插件对 meta 的 match（心跳插件不是系统插件，如 ff_news/weekly_report）——**实现取后者**（快照 = allowed_plugins 全集），因为 Operation.execute 的 is_enabled 已按插件过滤，meta 分支只需去掉 `event_type != "meta"` 的豁免即可。设计上标注：这是对 `plugin_pool` 一行的改动，行为差异 = 不在全集的心跳插件不再执行
- 全局单次任务（shop_weekly_rotation 等）在多群部署下仍单次执行（semantics 不变，per specs/plugins.md 附录"全局单次"栏）
- 按群遍历任务（批次 2 的 activity_timer 等）不在本提案——它们尚未做多群化

### D3：配置校验按服务而非按版名

`_REQUIRED_BOT` 收缩为进程启动必需（qq/nickname/super_users/ws_url/ws_token/两个 data_path/auth.salt）；其余必填项绑定到"该服务是否启用"：

| 键组 | 判定条件 |
|---|---|
| timeline.url + token | `timeline.url` 非空时成对必填 |
| onebot.http_url + token | `onebot.http_url` 非空时成对必填 |
| bot.default_group | 不再必填（社区/私有一致）；空 = 发送兜底丢弃（T0.2 已实现） |

`edition` 键：读取保留（向后兼容），仅作日志描述；`_EDITIONS` 白名单校验与 `_REQUIRED_PRIVATE_EXTRA` 分侧逻辑删除。冷却默认统一 0，社区模板写 3。

### D4：功能包数据化的最小形态

- `core/feature_packs.py` 的 `FEATURE_PACKS` 常量保留为缺省（私有零变化）
- 新增 `bot.feature_packs_file`：yaml 文件，结构 `{"包名": {"plugins": [..]}, ...}`，加载后整体替换（同 system_plugins 的"精确替换"语义先例）
- `/功能包` 指令、监控面板展示自动跟随（它们读的都是同一数据源）
- 不做按包启停的粒度配置（包内插件仍逐个经 group_plugin_config）——避免发明第五套开关

## 线程与事务

无新线程。allowed_plugins 为进程启动时冻结的 frozenset（config 是只读的），快照相交是纯内存操作，无锁。plugin_dispatch 的 Operation 已有线程隔离契约不变。

## 兼容与迁移

- 旧私有 config：无新键 → allowed_plugins=全集、包表=内置、校验收缩只放松不收紧 → 行为不变
- .103 私有部署升级路径：拉代码重启即可，无需改 config
- 社区 NAS 部署：模板写 `allowed_plugins: [checkin, checkin_recall, roll_back, remedy_checkin, week_checkin_display, all_checkin_display, week_list, personal_records, leaderboard, menu, backup, monitor, update, register(未来)]` + `feature_packs_file` 指向社区包定义——首版范围（config-only 核查"首版范围纠偏"）直接由这两个键表达

## 测试策略

- `test_deployment_gating.py`：三级叠加矩阵（部署关/开 × 群关/开 × 账号三态）、meta 事件路径、冲突启动报错、私有缺省零变化
- `test_config_loader.py` 扩展：服务化必填判定、edition 值无关性
- `test_feature_packs_config.py`：文件加载、回落、指令一致性
- 既有 533 项全量回归 = 行为不变的证明
