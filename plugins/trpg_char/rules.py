# DND 5E PHB 核心规则数据（种族/职业/背景/技能）

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
    "洞察": "感知",
    "生存": "感知",
    "欺瞒": "魅力",
    "威吓": "魅力",
    "游说": "魅力",
    "表演": "魅力",
}

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

# 职业：HP骰面数、可熟练技能数、初始装备
CLASSES = {
    "野蛮人": {"hp_die": 12, "skill_count": 2,
              "equipment": ["巨斧", "手斧×2", "探索者装备包", "标枪×4"]},
    "吟游诗人": {"hp_die": 8, "skill_count": 3,
                "equipment": ["细剑", "匕首", "乐器", "冒险者装备包"]},
    "牧师": {"hp_die": 8, "skill_count": 2,
            "equipment": ["钉头锤", "盾牌", "圣徽", "牧师装备包"]},
    "德鲁伊": {"hp_die": 8, "skill_count": 2,
              "equipment": ["木杖", "皮甲", "探索者装备包"]},
    "战士": {"hp_die": 10, "skill_count": 2,
            "equipment": ["链甲", "盾牌", "长剑", "标枪×2", "探索者装备包"]},
    "武僧": {"hp_die": 8, "skill_count": 2,
            "equipment": ["短剑×2", "探索者装备包", "短弓"]},
    "圣武士": {"hp_die": 10, "skill_count": 2,
              "equipment": ["长剑", "盾牌", "圣徽", "贵族装备包"]},
    "游侠": {"hp_die": 10, "skill_count": 3,
            "equipment": ["长剑×2", "箭袋+箭×20", "皮甲", "探索者装备包"]},
    "游荡者": {"hp_die": 8, "skill_count": 4,
              "equipment": ["短剑×2", "皮甲", "盗贼工具", "探索者装备包"]},
    "术士": {"hp_die": 8, "skill_count": 2,
            "equipment": ["轻型弩", "弩矢×20", "法术法器", "探索者装备包"]},
    "邪术师": {"hp_die": 8, "skill_count": 2,
              "equipment": ["轻型弩", "弩矢×20", "法术法器", "学者装备包"]},
    "法师": {"hp_die": 6, "skill_count": 2,
            "equipment": ["木杖", "法术书", "匕首", "学者装备包"]},
}

# 背景：两个技能熟练
BACKGROUNDS = {
    "侍僧": ["洞悉", "宗教"],
    "罪犯": ["欺瞒", "隐秘"],
    "艺人": ["杂技", "表演"],
    "民间英雄": ["驯兽", "生存"],
    "贵族": ["历史", "游说"],
    "流浪儿": ["巧手", "隐秘"],
    "贤者": ["奥术", "历史"],
    "水手": ["运动", "洞察"],
    "士兵": ["运动", "威吓"],
    "苦工": ["运动", "生存"],
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


def background_skills(background: str) -> list:
    return BACKGROUNDS.get(background, [])
