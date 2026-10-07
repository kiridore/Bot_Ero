# 配置统一化：部署行为完全由配置值决定

## Why

所有者已确认原则：社区与私有部署共用同一实现，行为只由实际配置值决定，不允许按版本名维护两套逻辑（`docs/community/config-only-plan-review.md`，2026-10-07）。当前遗留三处差距：

1. **meta 路径绕过部署级开关**：`main.py::plugin_pool` 中 meta 事件跳过 `operation.is_enabled` 检查——一批心跳插件（ff_news/weekly_report/startup_changelog/forum_notify）到达设定时间仍会执行，不受任何群/账号/部署开关限制。社区版审计（`specs/plugins.md` 附录 T0.9）已记录该风险，修复归属原定 T1.2，但当时方案仍是"社区白名单"，不符合新原则。
2. **配置校验按 edition 分侧**：`core/config.py` 按 `bot.edition` 决定必填键集合与冷却默认值——这是仅存的两处 edition 运行时分支。
3. **功能包表不可配置**：`core/feature_packs.py` 单表硬编码，包定义/默认开启集无法由配置数据决定；原 T0.7 "双表按版选择"方案已被 config-only 核查明确废止。

本提案将三者统一为"同一检查函数 + 配置数据驱动"，是 config-only 核查推荐顺序第 2 步，也为后续注册/审核/黑名单/频控（第 3 步）铺平分发层地基。

## What Changes

- **统一插件允许集合**：新增部署级"允许插件全集"概念（config 键 `bot.allowed_plugins`，缺省空 = 全部已注册插件，私有兼容）。`plugin_settings_snapshot` 在群/账号开关之上叠加该集合：不在全集内的插件对消息/通知/请求/notice/meta 全事件类型失效，心跳与内部通知一并停止。
- **meta 路径收口**：`plugin_pool` 对 meta 事件同样走 `operation.is_enabled`（快照对无群无账号的 meta 取部署级全集 ∩ 系统插件约定）。心跳类插件从此受部署开关约束；全局单次任务（shop_weekly_rotation/weekly_quest_reset/backup）语义不变。
- **配置校验去 edition 化**：必填键改为"按实际启用的服务检查"——`timeline.url` 有值才要求配套键、`webapp` 不跑则不要求网页侧参数；`edition` 键保留为纯描述标签，不参与任何控制流。冷却默认统一（缺省 0），差异进社区模板显式值。
- **功能包数据化**：`FEATURE_PACKS` 保留为兼容缺省，新增 config 键 `bot.feature_packs_file`（yaml，结构与现字典一致）允许部署自定义包定义与默认开启集；解析与管理逻辑单一，无双表选择。
- **私有零变化（硬底线）**：旧私有配置不补任何新键即可加载，行为与 1.51.0 逐项一致（空 allowed_plugins = 不裁剪；meta 收口后私有心跳插件全部在允许全集内，实际运行不变）。
- **权限硬限制不放松**：`/插件` `/功能包` 审核操作仍仅超级用户；系统插件保护与部署禁用的冲突按"部署禁用优先、启动时报错并列出冲突项"处理，不静默。

## Capabilities

- **New**：`deployment-gating`——部署级插件全集与全事件类型统一门控契约
- **Modified**：`system-plugins`（meta 不再无条件直达）、`plugin-event-processing`（快照叠加部署全集）

## Impact

涉及 `core/config.py`、`core/context.py`、`core/plugin_dispatch.py`、`main.py`、`core/feature_packs.py`、`config.example.yaml`、新增社区配置模板；schema 无新增表（allowed_plugins 为进程内配置，不落库）。用户可见行为变化仅"部署禁用的心跳插件不再执行"（原为缺陷语义），记 CHANGELOG 并 bump minor。

## 验收标准

| 编号 | 独立验证命令 | 必须验证的结果 |
|---|---|---|
| AC01 | `python -m pytest test/test_deployment_gating.py -k meta` | meta 事件下，不在 allowed_plugins 的心跳插件不执行；在集合内者照常；私有缺省配置（不配该键）全部心跳照常 |
| AC02 | `python -m pytest test/test_deployment_gating.py` | 群/账号/部署三级开关叠加语义正确：部署禁用优先于群开启；系统插件身份不能绕过部署禁用；冲突配置启动报错并列出冲突项 |
| AC03 | `python -m pytest test/test_config_loader.py test/test_config_wiring.py` | 旧私有配置零新增键可加载、行为不变；必填校验按实际启用服务判定（无 timeline.url 不报错，有则要求配套）；edition 为任意值/缺失不影响校验与默认值 |
| AC04 | `python -m pytest test/test_feature_packs_config.py` | feature_packs_file 自定义包生效；未配置时回落内置表；`/功能包 列表` 展示与配置一致；无第二处硬编码包表 |
| AC05 | `python -m pytest`（全量） | 全量回归绿；含 plugin-event-dispatch 既有 533 项 |
| AC06 | 同一测试套件换配置矩阵跑 | 同一有效配置仅改 edition 标签，全部断言结果一致（config-only 核查"共同验收规则"第 1、2 条落地） |
| AC07 | 审阅 `specs/plugins.md` 附录更新 + `kb/QUICK_REFERENCE.md` | 心跳插件三栏归类表更新为"受部署门控"；文档与实现一致，无"社区白名单"残留表述 |
| AC08 | `openspec validate config-unification --strict` | 提案校验通过 |

## 后续（不在本提案范围）

- 注册/群审核/黑名单/频控按统一配置实施（config-only 核查第 3 步，另建提案）
- 社区配置模板定稿与首版功能范围纠偏（第 4 步）
