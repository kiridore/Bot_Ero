import sqlite3

from core.base import CommandPlugin
from core.cq import text
from core.utils import register_plugin
import core.context as runtime_context
from core.feature_packs import FEATURE_PACKS


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


def _resolve_group(cmd_args: list[str], current_gid: int | None) -> int | None:
    if cmd_args and cmd_args[-1].isdigit():
        return int(cmd_args[-1])
    return current_gid


def _find_pack(name: str) -> str | None:
    for key in FEATURE_PACKS:
        if name == key or name in key:
            return key
    return None


@register_plugin
class GroupManagerPlugin(CommandPlugin):
    COMMANDS = (
        "/群插件列表", "/启用插件", "/禁用插件",
        "/全局插件列表", "/全局启用", "/全局禁用",
        "/功能包列表", "/开启功能包", "/关闭功能包",
        "/全局功能包列表", "/全局开启功能包", "/全局关闭功能包",
    )

    def handle(self):
        if not self.super_user():
            self.api.send_msg(text("仅超级用户可管理插件"))
            return

        cmd = self.cmd
        args = self.args
        gid = self.bot_event.group_id

        if cmd in ("/群插件列表",):
            target = _resolve_group(args, gid)
            if target is None:
                self.api.send_msg(text("请在群聊中使用，或指定群号"))
                return
            self.api.send_msg(text(_list_plugins_text(target)))

        elif cmd in ("/全局插件列表",):
            self.api.send_msg(text(_list_plugins_text(0)))

        elif cmd in ("/启用插件", "/禁用插件"):
            if not args:
                self.api.send_msg(text(f"用法：{cmd} <插件名> [群号]"))
                return
            name = args[0]
            target = _resolve_group(args[1:], gid)
            if target is None:
                self.api.send_msg(text("请在群聊中使用，或指定群号"))
                return
            enable = cmd == "/启用插件"
            _set_config(target, name, enable)
            self.api.send_msg(text(f"已{'启用' if enable else '禁用'}插件「{name}」"))

        elif cmd in ("/全局启用", "/全局禁用"):
            if not args:
                self.api.send_msg(text(f"用法：{cmd} <插件名>"))
                return
            enable = cmd == "/全局启用"
            _set_config(0, args[0], enable)
            self.api.send_msg(text(f"已全局{'启用' if enable else '禁用'}插件「{args[0]}」"))

        elif cmd in ("/功能包列表",):
            target = _resolve_group(args, gid)
            if target is None:
                self.api.send_msg(text("请在群聊中使用，或指定群号"))
                return
            self.api.send_msg(text(_list_packs_text(target)))

        elif cmd in ("/全局功能包列表",):
            self.api.send_msg(text(_list_packs_text(0)))

        elif cmd in ("/开启功能包", "/关闭功能包"):
            if not args:
                self.api.send_msg(text(f"用法：{cmd} <功能包名> [群号]"))
                return
            name = args[0]
            target = _resolve_group(args[1:], gid)
            if target is None:
                self.api.send_msg(text("请在群聊中使用，或指定群号"))
                return
            pack_key = _find_pack(name)
            if pack_key is None:
                names = "\n".join(FEATURE_PACKS)
                self.api.send_msg(text(f"未找到功能包「{name}」\n可用：\n{names}"))
                return
            enable = cmd == "/开启功能包"
            ok = _set_pack_config(target, pack_key, enable)
            self.api.send_msg(text(f"已{'开启' if enable else '关闭'}功能包「{pack_key}」"))

        elif cmd in ("/全局开启功能包", "/全局关闭功能包"):
            if not args:
                self.api.send_msg(text(f"用法：{cmd} <功能包名>"))
                return
            name = args[0]
            pack_key = _find_pack(name)
            if pack_key is None:
                names = "\n".join(FEATURE_PACKS)
                self.api.send_msg(text(f"未找到功能包「{name}」\n可用：\n{names}"))
                return
            enable = cmd == "/全局开启功能包"
            _set_pack_config(0, pack_key, enable)
            self.api.send_msg(text(f"已全局{'开启' if enable else '关闭'}功能包「{pack_key}」"))
