# Tasks · 称号前缀注入钩子化（T0.6）

> 验收标准见 proposal.md（5 条）；纯重构记 CHANGELOG `[未发布]` 不 bump。

- [x] 1. `core/context.py`：TITLE_PREFIX_PROVIDER + register_title_prefix_provider
- [x] 2. `plugins/title/__init__.py`：build_title_prefix 逐字迁入 + 模块级注册
- [x] 3. `core/api.py`：_build_title_prefix 改调 provider（未注册 → ""）
- [x] 4. 新增 `test/test_title_prefix_hook.py`（注入/未注册/异常三向）
- [x] 5. 验收 1：`rg -n "plugins" core/api.py` 零命中
- [x] 6. 全量 `pytest` 绿
- [x] 7. CHANGELOG `[未发布]`；development-plan 勾选 T0.6；`openspec archive title-prefix-hook`，同 commit：`refactor(称号): 前缀注入改为注册式钩子解除 core 反向依赖`
