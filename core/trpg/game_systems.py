"""跑团规则注册表：规则 id、展示名与检定入口。

新增规则 = 这里加一项 + 在 plugins/trpg_dice 里实现对应 check_handler，
并在网页规则展示里自动跟随（网页读 name）。
"""

DEFAULT_RULE = "dnd5e"

GAME_SYSTEMS = {
    "dnd5e": {
        "name": "DND 5E",
        "check_cmd": ".rc",
        "check_handler": "_handle_dnd_check",
        "check_usage": ".rc [优势|劣势] <属性|表达式> [豁免]",
        "aliases": ("dnd", "5e", "dnd5e", "dnd5th"),
    },
    "coc7th": {
        "name": "COC 7th",
        "check_cmd": ".ra",
        "check_handler": "_handle_coc_check",
        "check_usage": ".ra <技能值>",
        "aliases": ("coc", "coc7", "coc7th", "7th"),
    },
}


def rule_name(rule_id: str) -> str:
    """规则展示名；未知 id 原样返回（旧记录可能带已下线的规则名）。"""
    return GAME_SYSTEMS.get(rule_id, {}).get("name", rule_id)


def normalize_rule(text: str) -> str | None:
    """把用户输入（含大小写变体与别名）规范成规则 id；无法识别返回 None。"""
    key = (text or "").strip().lower()
    if not key:
        return None
    for rule_id, cfg in GAME_SYSTEMS.items():
        if key == rule_id or key in cfg.get("aliases", ()):
            return rule_id
    return None
