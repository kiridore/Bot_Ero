# 系统插件集配置化（社区版 T0.4）

## Why

系统插件（不可按群禁用）当前以 8 项 frozenset 硬编码在 `core/context.py`。社区版需裁剪该集合（不含 `message_logger`/`startup_changelog`/`auto_friend`/`welcome`，换入 `register` 等，见 T1.7 模板），差异只允许走 config 接缝（D5 白名单第 1 处）。config 侧键 `bot.system_plugins` 已由 T0.1 预埋（`core/config.py::SYSTEM_PLUGINS_CONF`），本提案接线消费侧。对应 `docs/community/development-plan.md` T0.4（M0 清障）。

## What Changes

- `core/context.py`：`SYSTEM_PLUGINS` 改读 `config.SYSTEM_PLUGINS_CONF`——非空 = 精确替换为配置列表；空/缺省 = 内置缺省集（现 8 项，常量保留为 `_DEFAULT_SYSTEM_PLUGINS`）
- `config.example.yaml`：`system_plugins` 注释补精确替换语义说明
- **私有形态零变化（硬底线 #122）**：私有配置无该键 → 缺省集 = 现值，行为逐字节一致

> **Ruling（可推翻）**：版本记录按近期先例（Docker、`mail.proxy` 均记 `[未发布]` 未单独 bump）处理——本变更为部署者面配置能力、私有行为零变化，记 `[未发布]` 不 bump，发布点统一 bump。

## Capabilities

- **New Capabilities**：`system-plugins`——系统插件集合的配置契约（缺省语义、精确替换、移出后回归按群开关机制）
- **Modified Capabilities**：无（消费方 main.py `plugin_pool` / `group_manager` / `web_panel` 全部经 `runtime_context.SYSTEM_PLUGINS` 属性引用，零改动）

## 验收标准

1. **缺省零变化**：配置无 `bot.system_plugins` 键（或空列表）时 `SYSTEM_PLUGINS` 等于现内置 8 项 `{menu, group_manager, startup_changelog, backup, update, auto_friend, welcome, message_logger}`——以新增测试断言 + 全量 pytest 绿共同证明
2. **配置精确生效**：`bot.system_plugins: [menu, register]` 时 `SYSTEM_PLUGINS == frozenset({menu, register})`（替换而非并集）
3. **移出即回归按群机制**：`message_logger` 不在配置集合时，`is_plugin_enabled` 对其不再短路返回 True（走 `group_plugin_config` 数据库路径）
4. **单数据源**：全仓 `rg SYSTEM_PLUGINS` 无第二处硬编码集合定义（消费面全部经 `runtime_context.SYSTEM_PLUGINS`）
5. **全量 `pytest` 绿**（私有形态回归，红线 #122）
