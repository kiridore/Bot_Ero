# 设计 · 系统插件集配置化（T0.4）

## 改动（一处数据源）

```python
# core/context.py
_DEFAULT_SYSTEM_PLUGINS = frozenset({  # 现 8 项原样保留
    "menu", "group_manager", "startup_changelog", "backup",
    "update", "auto_friend", "welcome", "message_logger",
})
# 系统级插件（不可按群禁用，始终运行）；bot.system_plugins 非空 = 精确替换
SYSTEM_PLUGINS = (
    frozenset(_config.SYSTEM_PLUGINS_CONF) if _config.SYSTEM_PLUGINS_CONF
    else _DEFAULT_SYSTEM_PLUGINS
)
```

消费方零改动（全部属性访问，已核实）：`core/context.py::is_plugin_enabled`（模块内全局）、`main.py::plugin_pool`（`runtime_context.is_plugin_enabled`）、`plugins/group_manager/__init__.py:44,79`（🔒 展示）、`core/web_panel.py:123,245`（监控面板）。

## 测试策略（`test/test_context_system_plugins.py`）

conftest 生成的临时配置无 `system_plugins` 键 → 直接断言缺省集（验收 1）。
自定义集合用 `importlib.reload(core.context)` + `mock.patch.object(core.config, "SYSTEM_PLUGINS_CONF", [...])`：reload 原地重执行模块，所有消费方经属性访问不受影响；finally 再 reload 回真实配置还原（验收 2）。
移出语义（验收 3）：reload 后直接调 `context.is_plugin_enabled`——系统集合内插件无 DB 行返回 True；移出后无 DB 行走 sqlite 路径返回 False（临时库无该行）。
单数据源（验收 4）：`rg -n "SYSTEM_PLUGINS"` 目视核对，不留第二处硬编码。

## 边界

- `SYSTEM_PLUGINS_CONF` 已是 `[str(s) for s in ...]` 规范化列表，无需再清洗
- 社区模板的具体落值（T1.7）不在本提案范围：本提案只交付"可配置"能力本身
