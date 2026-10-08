# 与 /菜单 回复一致；由 plugins/menu/entries.py 结构化条目渲染生成（config-unification）。
# 保留此常量供既有引用与测试断言；菜单实际渲染按有效插件过滤，见 entries.render_menu。
from core.config import NICKNAME

from .entries import SECTIONS


def _all_lines() -> list[str]:
    lines = [f"{NICKNAME}指令菜单", "---------------------------"]
    for title, entries in SECTIONS:
        lines.append(title)
        lines.extend(e[0] for e in entries)
    return lines


BOT_MENU_TEXT = "\n".join(_all_lines())
