import sqlite3

from core.base import CommandPlugin
from core.cq import text
from core.utils import register_plugin
import core.context as runtime_context
from core import config
from core.feature_packs import FEATURE_PACKS
from core.db.plugin_settings import set_user_plugins
from plugins.group_manager.status import query_text

ACTIONS = {"on": "on", "开启": "on", "off": "off", "关闭": "off"}


def _set_config(group_id: int, plugin_name: str, enable: bool):
    conn = sqlite3.connect(str(config.DB_PATH))
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


def _set_pack_config(group_id: int, pack_name: str, enable: bool):
    pack = FEATURE_PACKS.get(pack_name)
    if pack is None:
        return False
    conn = sqlite3.connect(str(config.DB_PATH))
    try:
        with conn:
            for key in pack["plugins"]:
                if key in runtime_context.SYSTEM_PLUGINS:
                    continue
                if enable and not runtime_context.plugin_allowed(key):
                    continue  # 部署未开放的成员不开后门；关闭操作仍允许清理旧开启行
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
        return True
    finally:
        conn.close()


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
            return (f"用法：{self.cmd} <名称|列表> [off|关闭] [群号]\n"
                    f"账号设置：{self.cmd} <名称> <开启|关闭|默认> 用户 <账号>\n"
                    f"账号列表：{self.cmd} 列表 用户 <账号>\n"
                    f"公共默认：{self.cmd} 列表 公共默认（兼容 列表 0）\n"
                    "无目标列表：私聊查本人，群聊查本群；私聊无目标开启/关闭仍修改公共默认，影响继承账号\n"
                    "默认表示沿用私聊公共设置；只有超级用户可以查询和修改")
        first = self.args[0]
        rest = self.args[1:]
        action = "on"
        clean = []
        for a in rest:
            if a in ACTIONS:
                action = ACTIONS[a]
            else:
                clean.append(a)
        if (len(clean) > 1 or (clean and (not clean[0].isascii() or not clean[0].isdigit()
                or len(clean[0]) > 19 or int(clean[0]) > 9223372036854775807))):
            return "群号须为非负整数；账号设置请使用 用户 <账号>"
        gid = self.bot_event.group_id
        target_gid = _resolve_target_gid(clean, gid)
        return first, action, target_gid

    def handle(self):
        if not self.super_user():
            self.api.send_msg(text("仅超级用户可管理插件"))
            return
        if self.args and self.args[0] == "列表":
            self._query()
            return
        if "用户" in self.args or "群" in self.args:
            self._explicit_target()
            return
        if "默认" in self.args:
            self.api.send_msg(text("恢复默认仅用于：/插件 <名称> 默认 用户 <账号>"))
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

    def _query(self):
        tail = [arg for arg in self.args[1:] if arg not in ACTIONS and arg != '默认']
        scope, target = None, None
        if not tail:
            scope = 'group' if self.bot_event.group_id is not None else 'user'
            target = self.bot_event.group_id if scope == 'group' else self.bot_event.user_id
        elif tail in (['公共默认'], ['0']):
            scope = 'defaults'
        elif len(tail) == 1:
            scope, target = 'group', tail[0]
        elif len(tail) == 2 and tail[0] in ('用户', '群'):
            scope, target = ('user' if tail[0] == '用户' else 'group'), tail[1]
        if scope != 'defaults':
            number = str(target)
            if (scope is None or not number.isascii() or not number.isdecimal()
                    or len(number) > 19 or not 0 < int(number) <= 9223372036854775807):
                self.api.send_msg(text(f'用法：{self.cmd} 列表 [用户 <账号>|群 <群号>|公共默认]'))
                return
            target = int(number)
        self.api.send_msg(text(query_text(scope, target, FEATURE_PACKS, self.cmd == '/功能包')))

    def _explicit_target(self):
        args = self.args
        if (len(args) not in (3, 4) or args[-2] not in ("群", "用户")
                or not args[-1].isascii() or not args[-1].isdigit() or len(args[-1]) > 19
                or not 0 < int(args[-1]) <= 9223372036854775807):
            self.api.send_msg(text(f"用法：{self.cmd} <名称> <开启|关闭|默认> <群|用户> <编号>；列表可省略动作"))
            return
        name, scope, target = args[0], args[-2], int(args[-1])
        action = ACTIONS.get(args[1]) if len(args) == 4 else "on"
        if len(args) == 4 and args[1] == "默认":
            action = "default"
        if action is None or (name != "列表" and len(args) != 4):
            self.api.send_msg(text("请明确指定开启、关闭或默认"))
            return
        if scope == "群":
            if action == "default":
                self.api.send_msg(text("群设置不支持账号的恢复默认操作"))
                return
            if self.cmd == "/插件":
                self._plugin(name, action, target)
            else:
                self._pack(name, action, target)
            return
        conn = sqlite3.connect(str(config.DB_PATH))
        try:
            if self.cmd == "/功能包":
                pack = _find_pack(name)
                if pack is None:
                    self.api.send_msg(text(f"功能包「{name}」不存在"))
                    return
                names = [key for key in FEATURE_PACKS[pack]["plugins"]
                         if key not in runtime_context.SYSTEM_PLUGINS]
            else:
                if name not in _all_plugin_names():
                    self.api.send_msg(text(f"插件「{name}」不存在"))
                    return
                if name in runtime_context.SYSTEM_PLUGINS:
                    self.api.send_msg(text("系统插件不支持账号覆盖设置"))
                    return
                if not runtime_context.plugin_allowed(name):
                    self.api.send_msg(text(f"插件「{name}」未在本部署开放，不能设置；如需开放请修改配置 allowed_plugins"))
                    return
                names = [name]
            set_user_plugins(conn, target, names, None if action == "default" else action == "on")
            label = {"on": "开启", "off": "关闭", "default": "恢复默认"}[action]
            self.api.send_msg(text(f"已为用户{target}{label}「{name}」"))
        finally:
            conn.close()

    def _plugin(self, name: str, action: str, target_gid: int):
        valid = _all_plugin_names()
        if name not in valid:
            lines = "\n".join(sorted(valid))
            self.api.send_msg(text(f"插件「{name}」不存在\n可用插件：\n{lines}"))
            return
        if name in runtime_context.SYSTEM_PLUGINS:
            self.api.send_msg(text("系统插件始终运行，不支持单独开关"))
            return
        if not runtime_context.plugin_allowed(name):
            self.api.send_msg(text(f"插件「{name}」未在本部署开放，不能开启或关闭；如需开放请修改配置 allowed_plugins"))
            return
        enable = action == "on"
        _set_config(target_gid, name, enable)
        scope = "私聊公共默认（影响继承账号）" if target_gid == 0 else f"群{target_gid}"
        self.api.send_msg(text(f"已{scope}{'启用' if enable else '禁用'}插件「{name}」"))

    def _pack(self, name: str, action: str, target_gid: int):
        pk = _find_pack(name)
        if pk is None:
            lines = "\n".join(FEATURE_PACKS)
            self.api.send_msg(text(f"功能包「{name}」不存在\n可用功能包：\n{lines}"))
            return
        enable = action == "on"
        _set_pack_config(target_gid, pk, enable)
        scope = "私聊公共默认（影响继承账号）" if target_gid == 0 else f"群{target_gid}"
        self.api.send_msg(text(f"已{scope}{'开启' if enable else '关闭'}功能包「{pk}」"))
