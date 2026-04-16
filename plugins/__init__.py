"""
plugins 包初始化：

- 自动导入同目录下所有子模块（确保插件类上的 @register_plugin 执行）
- 根据全局 plugin_registry 动态生成 __all__，减少手工维护
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING

from core import context as _runtime_context

if TYPE_CHECKING:
    from core.base import Plugin as _Plugin


def _load_all_plugin_modules() -> None:
    """导入当前包下的所有模块，以触发插件注册装饰器。"""
    package_name = __name__
    for finder, name, is_pkg in pkgutil.walk_packages(__path__, prefix=package_name + "."):  # type: ignore[name-defined]
        if is_pkg:
            continue
        importlib.import_module(name)


_load_all_plugin_modules()

# 按注册表里的插件类名导出，主要为了类型提示友好；实际分发逻辑走 plugin_registry
__all__ = [cls.__name__ for cls in _runtime_context.plugin_registry]  # type: ignore[misc]

