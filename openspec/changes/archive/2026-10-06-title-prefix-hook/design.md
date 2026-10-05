# 设计 · 称号前缀注入钩子化（T0.6）

## 三点接线

```python
# core/context.py（SYSTEM_PLUGINS 块后）
TITLE_PREFIX_PROVIDER = None  # plugins.title 加载时注册；未注册 = 无称号前缀（社区裁剪形态）

def register_title_prefix_provider(fn) -> None:
    global TITLE_PREFIX_PROVIDER
    TITLE_PREFIX_PROVIDER = fn

# plugins/title/__init__.py（模块级，import 期注册）
def build_title_prefix(dbmanager, user_id: int) -> str:
    try:
        equipped = dbmanager.titles.equipped_all(user_id)[:3]
        names = [d["name"] for tid in equipped if (d := get_title_def(tid)) and d.get("name")]
        return "「{}」".format("·".join(names)) if names else ""
    except Exception:
        return ""

runtime_context.register_title_prefix_provider(build_title_prefix)

# core/api.py
def _build_title_prefix(self, user_id):
    provider = runtime_context.TITLE_PREFIX_PROVIDER
    if provider is None:
        return ""
    return provider(self.dbmanager, user_id)
```

（实现以现函数体为准逐字迁移，上面的 walrus 合并仅示意；格式 `「a·b·c」` 与 [:3] 截断不变。）

## 关键语义

- **Ruling（实现期裁定，修正 design 初稿）**：异常吞没单点放在 api 接缝（`_build_title_prefix` try/except 包裹 provider 调用）而非 provider 体内——接缝守卫保护任意未来 provider，title 侧 `build_title_prefix` 保持纯函数；对外语义与旧实现（整体吞没返回 ""）逐字节等价

- **注册时机**：bot 进程 `plugins/__init__.py` walk 导入 plugins.title 时模块级注册（checkin/lottery 等的 import 也触发，幂等覆盖）；webapp 进程 title_loader 以独立包名加载 __init__，注册同样发生但无消费者，无害
- **降级等价**：现状 import 失败 → try/except → ""；钩子形态 provider=None → ""。title 插件被裁剪时行为一致
- **self.dbmanager 传入 provider**：保持 title 侧不持有 DB 句柄（与现状一致，api 实例持有）

## 测试策略（`test/test_title_prefix_hook.py`，in-process）

1. 注册 fake provider（返回「甲·乙」）→ ApiWrapper 实例调 `_inject_titles_before_at([at(qq), text("hi")])` 断言首段为 `text("「甲·乙」")`
2. `TITLE_PREFIX_PROVIDER = None`（setUp 保存/tearDown 还原）→ 同调用消息原样、无前缀段
3. provider 抛 RuntimeError → `_build_title_prefix` 返回 ""（不外抛）
