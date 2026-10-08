"""功能包定义：内置缺省 + bot.feature_packs_file 整体替换（config-unification）。

包只定义"哪些插件属于一组"，方便超级用户批量设置；不自动开启、不是权限层。
"""
import sys
from pathlib import Path

import yaml

from core import config

_BUILTIN_PACKS = {
    "基础包": {
        "plugins": [
            "checkin", "checkin_recall", "roll_back", "remedy_checkin",
            "week_checkin_display", "all_checkin_display", "week_list",
            "personal_records", "leaderboard",
        ],
    },
    "基础扩展包": {
        "plugins": [
            "lottery", "redeem_shop", "grant_points_all",
            "title",
            "weekly_quest",
            "immortal_lottery",
        ],
    },
    "休闲娱乐": {
        "plugins": ["ff_news", "group_alarm", "dice", "divination", "random_reference", "call"],
    },
    "匿名游戏": {
        "plugins": ["who_is_spy"],
    },
    "跑团": {
        "plugins": ["trpg_dice", "trpg_session", "trpg_char"],
    },
    "群管理工具": {
        "plugins": ["group_essence", "at_all_reply", "recall_message", "set_group_title"],
    },
}


def _normalize(value, name: str, path: Path) -> dict:
    plugins = value.get("plugins") if isinstance(value, dict) else value
    if (not isinstance(plugins, list) or not plugins
            or not all(isinstance(s, str) and s.strip() for s in plugins)):
        sys.exit(
            f"功能包文件 {path} 无效：包「{name}」必须是插件标识的非空字符串列表"
            f"（或 plugins: [..] 映射）")
    return {"plugins": [str(s) for s in plugins]}


def _load_configured(file_str: str) -> dict:
    path = Path(file_str)
    if not path.is_absolute():
        path = config.CONFIG_PATH.parent / path  # 相对路径以主配置所在目录为基准
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        sys.exit(f"bot.feature_packs_file 指向的文件不存在：{path}")
    except yaml.YAMLError as exc:
        sys.exit(f"功能包文件 {path} 不是有效 YAML：{exc}")
    if not isinstance(data, dict) or not data:
        sys.exit(f"功能包文件 {path} 顶层必须是非空映射：包名 → [插件标识] 或 {{plugins: [...]}}")
    return {str(name): _normalize(value, str(name), path) for name, value in data.items()}


FEATURE_PACKS = _load_configured(config.FEATURE_PACKS_FILE) if config.FEATURE_PACKS_FILE else _BUILTIN_PACKS
