# Tasks · 系统插件集配置化（T0.4）

> 验收标准见 proposal.md，逐项对应；全量 pytest 绿为出口（红线 #122）。

- [x] 1. `core/context.py`：`_DEFAULT_SYSTEM_PLUGINS` 常量 + `SYSTEM_PLUGINS` 按 `SYSTEM_PLUGINS_CONF` 接线（空回落缺省）
- [x] 2. 新增 `test/test_context_system_plugins.py`：缺省集断言 / reload 自定义集合断言 / 移出项 `is_plugin_enabled` 回归 DB 路径断言（验收 1-3）
- [x] 3. `config.example.yaml` 注释补替换语义；`rg SYSTEM_PLUGINS` 核对单数据源（验收 4）
- [x] 4. 全量 `pytest` 绿（验收 5）
- [x] 5. CHANGELOG `[未发布]` 记条目（Ruling：不 bump）；`docs/community/development-plan.md` 勾选 T0.4
- [x] 6. `openspec archive system-plugins-config` 归档，与实现同一 commit：`feat(插件): 系统插件集合改为 config 配置`
