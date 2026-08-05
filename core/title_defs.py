"""称号定义：从 plugins/title/defs.py 加载一次，全 Web 子应用共享。"""

from pathlib import Path
import importlib.util

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFS_PATH = _PROJECT_ROOT / "plugins" / "title" / "defs.py"


def _load() -> dict:
    spec = importlib.util.spec_from_file_location("botero_title_defs", _DEFS_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "TITLE_DEFS", {})


TITLE_DEFS: dict = _load()
