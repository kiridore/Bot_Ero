# 从共享模块 re-export，保持旧 import 路径兼容（trpg_dice/trpg_session 仍引用）
from core.trpg.character import (  # noqa: F401
    finalize,
    get_attr_value,
    resolve_expression_values,
    format_sheet,
)
