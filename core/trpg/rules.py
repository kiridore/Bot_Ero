# DND 5E 核心规则数据（种族/职业/技能）
# 仅保留骰子系统依赖的数值化数据；特性/物品/剧情等自由内容由角色卡备注字段管理

ATTRIBUTES = ["力量", "敏捷", "体质", "智力", "感知", "魅力"]

ATTRIBUTE_EN = {
    "力量": "str", "敏捷": "dex", "体质": "con",
    "智力": "int", "感知": "wis", "魅力": "cha",
}

# 技能 → 关联属性
SKILLS = {
    "运动": "力量",
    "杂技": "敏捷",
    "巧手": "敏捷",
    "隐秘": "敏捷",
    "奥术": "智力",
    "历史": "智力",
    "调查": "智力",
    "自然": "智力",
    "宗教": "智力",
    "驯兽": "感知",
    "洞悉": "感知",
    "医药": "感知",
    "察觉": "感知",
    "生存": "感知",
    "欺瞒": "魅力",
    "威吓": "魅力",
    "游说": "魅力",
    "表演": "魅力",
}

# 技能别名（骰子引用时可用）
SKILL_ALIASES = {"侦查": "察觉"}

# 种族：属性加值 {"力量": 2, ...}，空字典表示无加值
RACES = {
    "人类": {"力量": 1, "敏捷": 1, "体质": 1, "智力": 1, "感知": 1, "魅力": 1},
    "精灵": {"敏捷": 2, "智力": 1},
    "矮人": {"体质": 2},
    "半身人": {"敏捷": 2},
    "半精灵": {"魅力": 2, "敏捷": 1},
    "半兽人": {"力量": 2, "体质": 1},
    "龙裔": {"力量": 2, "魅力": 1},
    "侏儒": {"智力": 2},
}

# 职业：仅 HP 骰面数与可熟练技能数（其余为自由内容）
CLASSES = {
    "野蛮人": {"hp_die": 12, "skill_count": 2},
    "吟游诗人": {"hp_die": 8, "skill_count": 3},
    "牧师": {"hp_die": 8, "skill_count": 2},
    "德鲁伊": {"hp_die": 8, "skill_count": 2},
    "战士": {"hp_die": 10, "skill_count": 2},
    "武僧": {"hp_die": 8, "skill_count": 2},
    "圣武士": {"hp_die": 10, "skill_count": 2},
    "游侠": {"hp_die": 10, "skill_count": 3},
    "游荡者": {"hp_die": 8, "skill_count": 4},
    "术士": {"hp_die": 8, "skill_count": 2},
    "邪术师": {"hp_die": 8, "skill_count": 2},
    "法师": {"hp_die": 6, "skill_count": 2},
}

# 标准购点成本：属性值 → 花费点数
POINT_BUY_COST = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
POINT_BUY_BUDGET = 27

# 标准数组
STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]


def ability_modifier(score) -> int:
    return (int(score) - 10) // 2


def skill_attribute(skill: str) -> str:
    return SKILLS.get(skill, "")


def race_bonuses(race: str) -> dict:
    return RACES.get(race, {})


def class_info(class_name: str) -> dict:
    return CLASSES.get(class_name, {})
