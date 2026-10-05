# 称号前缀注入钩子化（社区版 T0.6）

> 纯重构：行为零变化，skip_specs。**勘误**：任务原定"现有 @ 提及注入用例回归"——经核对 test/ 零覆盖，本提案自带新建双向断言。

## Why

`core/api.py::_build_title_prefix`（L49-64）内 `from plugins.title import get_title_def` 是 core→plugins 的反向依赖（架构耦合 C 类，T0.6 清障项）：core 语义上不该知道任何插件的存在。改为注册式钩子后 core 只暴露 `runtime_context.register_title_prefix_provider(fn)`，title 插件加载时自注册——与 T0.5 同向（core 去插件化），为社区形态裁剪 title 插件（若届时裁掉）解除隐式耦合。

## What Changes

- `core/context.py`：`TITLE_PREFIX_PROVIDER = None` + `register_title_prefix_provider(fn)`（赋值式注册，重复注册后者覆盖，无并发风险——注册只发生在 import 期）
- `plugins/title/__init__.py`：模块级注册 `build_title_prefix(dbmanager, user_id)`（函数体 = 现 api 侧实现逐字迁移：`equipped_all()[:3]` + `get_title_def` 取名 + `「a·b·c」` 拼接 + 整体 try/except 吞异常返回 ""）
- `core/api.py`：`_build_title_prefix` 改为 `runtime_context.TITLE_PREFIX_PROVIDER(self.dbmanager, user_id) if registered else ""`——未注册降级与现状（import 失败→""）等价
- **新增 `test/test_title_prefix_hook.py`**：注册 provider → @ 段前注入前缀；未注册 → 消息原样；provider 抛异常 → 前缀为空不炸

**不改**：`_inject_titles_before_at` 调用点与拼接格式；plugins/webapp 侧对 `get_title_def`/`equipped_all` 的直接引用（合法方向）；`plugins/title` 对外 `__all__`。

## Capabilities

- 无（纯重构，skip_specs: true）

## 验收标准

1. **core 出清**：`rg -n "plugins" core/api.py` 零命中（反向依赖消除）；`core/context.py` 具备 provider 注册点
2. **注册生效**：注册返回「甲·乙」的 provider 后，`_inject_titles_before_at` 对含 @ 段消息注入「甲·乙」text 前缀
3. **未注册降级**：`TITLE_PREFIX_PROVIDER = None` 时消息原样通过（与 title 插件不加载的社区裁剪形态等价）
4. **异常吞没保持**：provider 抛异常 → 前缀为空、不向外抛
5. **等价回归**：全量 `pytest` 绿（红线 #122）
