import sqlite3

from core.base import CommandPlugin
from core.cq import text
from core.utils import register_plugin
import core.context as runtime_context
from core.feature_packs import FEATURE_PACKS

ACTIONS = {"on": "on", "开启": "on", "off": "off", "关闭": "off"}


def _get_config(group_id: int) -> set[str]:
    conn = sqlite3.connect("data.db")
    rows = conn.execute(
        "SELECT plugin_name FROM group_plugin_config WHERE group_id = ?",
        (group_id,)
    ).fetchall()
    conn.close()
    return {row[0] for row in rows}


def _set_config(group_id: int, plugin_name: str, enable: bool):
    conn = sqlite3.connect("data.db")
    if enable:
        conn.execute(
            "INSERT OR IGNORE INTO group_plugin_config (group_id, plugin_name) VALUES (?, ?)",
            (group_id, plugin_name)
        )
    else:
        conn.execute(
            "DELETE FROM group_plugin_config WHERE group_id = ? AND plugin_name = ?",
            (group_id, plugin_name)
        )
    conn.commit()
    conn.close()


def _list_plugins_text(group_id: int) -> str:
    enabled = _get_config(group_id)
    lines = []
    for cls in runtime_context.plugin_registry:
        key = runtime_context.plugin_key(cls)
        if key in runtime_context.SYSTEM_PLUGINS:
            status = "🔒"
        elif key in enabled:
            status = "✅"
        else:
            status = "❌"
        lines.append(f"{status} {key}")
    return "\n".join(lines)


def _list_packs_text(group_id: int) -> str:
    enabled = _get_config(group_id)
    lines = []
    for name, pack in FEATURE_PACKS.items():
        pset = set(pack["plugins"])
        total = len(pset)
        on = len(pset & enabled)
        if on == 0:
            icon = "❌"
        elif on == total:
            icon = "✅"
        else:
            icon = "⚡"
        lines.append(f"{icon} {name} ({on}/{total})")
    lines.append("")
    lines.append("🔒 系统插件始终运行")
    return "\n".join(lines)


def _set_pack_config(group_id: int, pack_name: str, enable: bool):
    pack = FEATURE_PACKS.get(pack_name)
    if pack is None:
        return False
    conn = sqlite3.connect("data.db")
    for key in pack["plugins"]:
        if key in runtime_context.SYSTEM_PLUGINS:
            continue
        if enable:
            conn.execute(
                "INSERT OR IGNORE INTO group_plugin_config (group_id, plugin_name) VALUES (?, ?)",
                (group_id, key)
            )
        else:
            conn.execute(
                "DELETE FROM group_plugin_config WHERE group_id = ? AND plugin_name = ?",
                (group_id, key)
            )
    conn.commit()
    conn.close()
    return True


def _find_pack(name: str) -> str | None:
    for key in FEATURE_PACKS:
        if name == key or name in key:
            return key
    return None


def _all_plugin_names() -> set[str]:
    return {runtime_context.plugin_key(cls) for cls in runtime_context.plugin_registry}


def _resolve_target_gid(args_tail: list[str], gid: int | None) -> int:
    if args_tail and args_tail[-1].isdigit():
        return int(args_tail[-1])
    return gid if gid is not None else 0


@register_plugin
class GroupManagerPlugin(CommandPlugin):
    COMMANDS = ("/插件", "/功能包")

    def _parse(self) -> tuple[str, str, int] | str:
        if not self.args:
            return f"用法：{self.cmd} <名称|列表> [off|关闭] [群号]"
        first = self.args[0]
        rest = self.args[1:]
        action = "on"
        clean = []
        for a in rest:
            if a in ACTIONS:
                action = ACTIONS[a]
            else:
                clean.append(a)
        gid = self.bot_event.group_id
        target_gid = _resolve_target_gid(clean, gid)
        return first, action, target_gid

    def handle(self):
        if not self.super_user():
            self.api.send_msg(text("仅超级用户可管理插件"))
            return
        parsed = self._parse()
        if isinstance(parsed, str):
            self.api.send_msg(text(parsed))
            return
        name, action, target_gid = parsed
        if self.cmd == "/插件":
            self._plugin(name, action, target_gid)
        else:
            self._pack(name, action, target_gid)

    def _plugin(self, name: str, action: str, target_gid: int):
        if name == "列表":
            self.api.send_msg(text(_list_plugins_text(target_gid)))
            return
        valid = _all_plugin_names()
        if name not in valid:
            lines = "\n".join(sorted(valid))
            self.api.send_msg(text(f"插件「{name}」不存在\n可用插件：\n{lines}"))
            return
        enable = action == "on"
        _set_config(target_gid, name, enable)
        scope = "全局" if target_gid == 0 else f"群{target_gid}"
        self.api.send_msg(text(f"已{scope}{'启用' if enable else '禁用'}插件「{name}」"))

    def _pack(self, name: str, action: str, target_gid: int):
        if name == "列表":
            self.api.send_msg(text(_list_packs_text(target_gid)))
            return
        pk = _find_pack(name)
        if pk is None:
            lines = "\n".join(FEATURE_PACKS)
            self.api.send_msg(text(f"功能包「{name}」不存在\n可用功能包：\n{lines}"))
            return
        enable = action == "on"
        _set_pack_config(target_gid, pk, enable)
        scope = "全局" if target_gid == 0 else f"群{target_gid}"
        self.api.send_msg(text(f"已{scope}{'开启' if enable else '关闭'}功能包「{pk}」"))
