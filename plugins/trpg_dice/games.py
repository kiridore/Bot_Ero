# 游戏规则注册表
#
# 当前仅启用 DND 5E。未来加入规则切换时：
#   1. 在此注册新规则（如 coc7）
#   2. 在 TrpgPlugin 中实现对应检定处理器（check_handler）
#   3. 将 context.GAME_SYSTEM 切换为新规则名
#
# COC 7E 相关实现（.ra 技能检定、b/p 奖惩骰、coc_check）已移除，
# 历史代码见 git 记录，可随时恢复。

GAME_SYSTEMS = {
    "dnd5e": {
        "name": "DND 5E",
        "check_cmd": ".rc",
        "check_handler": "_handle_dnd_check",
        "check_usage": ".rc [优势|劣势] <属性|表达式> [豁免]",
    },
    # 示例：未来恢复 COC 7E
    # "coc7": {
    #     "name": "COC 7E",
    #     "check_cmd": ".ra",
    #     "check_handler": "_handle_coc_check",
    #     "check_usage": ".ra <技能值>",
    # },
}

DEFAULT_GAME_SYSTEM = "dnd5e"
