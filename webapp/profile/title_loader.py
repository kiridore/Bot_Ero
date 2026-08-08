"""动态加载 plugins/title 包（避免 `import plugins` 触发全部插件自动注册）。

插件目录重构（bca3283）后 title 逻辑位于 plugins/title/ 包内（logic.py 为纯逻辑，
__init__.py 为薄封装 + TitlePlugin）。网页端只需 evaluate_and_unlock_titles /
get_title_def，故以独立包名加载 __init__.py，并借助 submodule_search_locations
让包内相对导入（.defs / .logic）正常解析。
"""

import importlib.util
import sys
from types import ModuleType

from core import config

_TITLE_PKG = config.PROJECT_ROOT / "plugins" / "title"


def load_title_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "botero_title",
        _TITLE_PKG / "__init__.py",
        submodule_search_locations=[str(_TITLE_PKG)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("plugins/title 包无法加载")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["botero_title"] = mod
    spec.loader.exec_module(mod)
    return mod
