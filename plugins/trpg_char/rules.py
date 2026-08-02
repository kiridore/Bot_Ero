# 从共享模块 re-export，保持旧 import 路径兼容（trpg_dice/trpg_session 仍引用）
from core.trpg.rules import (  # noqa: F401
    ATTRIBUTES, ATTRIBUTE_EN, SKILLS, SKILL_ALIASES, RACES, CLASSES,
    POINT_BUY_COST, POINT_BUY_BUDGET, STANDARD_ARRAY,
    ability_modifier, skill_attribute, race_bonuses, class_info,
)
