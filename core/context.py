# 一些全局运行时数据
from datetime import datetime
from typing import TYPE_CHECKING
import sqlite3
from threading import Lock

if TYPE_CHECKING:
    from core.base import Plugin

script_start_time = datetime.now()
from core import config as _config

llonebot_data_path = _config.LLONEBOT_DATA_PATH    # 使用api是用这个地址（config.yaml）
python_data_path = _config.PYTHON_DATA_PATH        # 在python脚本中访问用这个地址（config.yaml）
onebot_qq_volume = _config.ONEBOT_QQ_VOLUME
startup_changelog_sent = True
plugin_registry: list[type["Plugin"]] = []
DEFAULT_GROUP_ID = _config.DEFAULT_GROUP_ID  # 固定群号（config.yaml bot.default_group）

# 系统级插件（不可按群禁用，始终运行）；bot.system_plugins 非空 = 精确替换，空/缺省 = 内置缺省集
_DEFAULT_SYSTEM_PLUGINS = frozenset({
    "menu",
    "group_manager",
    "startup_changelog",
    "backup",
    "update",
    "auto_friend",
    "welcome",
    "message_logger",
})
SYSTEM_PLUGINS = (
    frozenset(_config.SYSTEM_PLUGINS_CONF) if _config.SYSTEM_PLUGINS_CONF
    else _DEFAULT_SYSTEM_PLUGINS
)
# 部署允许范围（config-unification）：None = 兼容模式（全部已注册插件，旧配置零变化）；
# frozenset = 明确名单。冻结后只读；与注册表/系统集合的一致性由 validate_deployment_policy 保证。
ALLOWED_PLUGINS = frozenset(_config.ALLOWED_PLUGINS_CONF) if _config.ALLOWED_PLUGINS_CONF else None


def plugin_allowed(key: str) -> bool:
    """部署级硬边界：不在名单内的插件在任何事件类型、任何局部开关下都不可运行。"""
    return ALLOWED_PLUGINS is None or key in ALLOWED_PLUGINS


def validate_deployment_policy() -> None:
    """在全部插件完成自动导入后、start_panel/事件接收前调用（main.py）。

    校验部署策略引用与冲突，失败即退出，不静默取舍：
    - allowed_plugins/system_plugins 引用的标识必须真实存在（防拼错悄悄失效）；
    - 生效系统集合必须是部署允许子集（防偷偷启用）；
    - 注册表为空说明调用时机错误（不能把"全部插件"冻结成空集）。
    """
    import sys
    registered = {plugin_key(cls) for cls in plugin_registry}
    problems: list[str] = []
    if not registered:
        problems.append("插件注册表为空：部署策略校验必须在 import plugins 之后调用")
    if _config.SYSTEM_PLUGINS_CONF:
        unknown_sys = sorted(set(_config.SYSTEM_PLUGINS_CONF) - registered)
        if unknown_sys:
            problems.append(f"bot.system_plugins 含未注册插件：{', '.join(unknown_sys)}")
    if ALLOWED_PLUGINS is not None:
        unknown_allowed = sorted(ALLOWED_PLUGINS - registered)
        if unknown_allowed:
            problems.append(f"bot.allowed_plugins 含未注册插件：{', '.join(unknown_allowed)}")
        conflicts = sorted(SYSTEM_PLUGINS - ALLOWED_PLUGINS)
        if conflicts:
            problems.append(f"系统插件不在 allowed_plugins 内：{', '.join(conflicts)}")
    if problems:
        sys.exit("部署配置校验失败：\n- " + "\n- ".join(problems))

# 称号前缀提供者（plugins.title 加载时注册；未注册 = 无称号前缀，社区裁剪形态降级）
TITLE_PREFIX_PROVIDER = None

def register_title_prefix_provider(fn) -> None:
    global TITLE_PREFIX_PROVIDER
    TITLE_PREFIX_PROVIDER = fn

# 跑团录制状态
recording_lock = Lock()
recording_sessions: dict[int, dict] = {}      # group_id → {"start": datetime, "messages": list, "participants": dict}
last_completed: dict[int, dict] = {}           # group_id → {"start": datetime, "end": datetime, "messages": list, "participants": dict}
RECORDING_ALLOWED_PLUGINS = frozenset({"trpg_dice", "trpg_session", "trpg_char"})

# 跑团角色：group_id → {user_id → "dm"|"ob"}
group_roles: dict[int, dict[str, str]] = {}

# 当前游戏规则系统（跑团骰子检定用），未来规则切换功能修改此值
GAME_SYSTEM = "dnd5e"

# 卧底游戏
game_lock = Lock()
game_rooms: dict[str, dict] = {}

def is_group_recording(group_id: int) -> bool:
    return group_id in recording_sessions

def get_recording_session(group_id: int) -> dict | None:
    return recording_sessions.get(group_id)

def get_last_completed(group_id: int) -> dict | None:
    return last_completed.get(group_id)

def pop_last_completed(group_id: int) -> dict | None:
    return last_completed.pop(group_id, None)

def is_plugin_allowed_during_recording(key: str) -> bool:
    return key in RECORDING_ALLOWED_PLUGINS

def plugin_key(plugin_cls: type["Plugin"]) -> str:
    return plugin_cls.__module__.split(".", 1)[1]

def plugin_settings_snapshot(group_id=None, user_id=None) -> dict[str, bool]:
    from core.database_manager import DbManager
    from core.db.plugin_settings import enabled_plugins
    db = DbManager()
    try:
        settings = enabled_plugins(db.conn, group_id, user_id)
    finally:
        db.conn.close()
    if ALLOWED_PLUGINS is not None:
        # 部署硬边界：不在名单内的插件对任何事件、任何局部开关都不可运行（config-unification）
        settings = {key: value for key, value in settings.items() if key in ALLOWED_PLUGINS}
    settings.update({key: True for key in SYSTEM_PLUGINS})
    return settings


def is_plugin_enabled(plugin_cls: type["Plugin"], group_id: int | None, user_id=None) -> bool:
    key = plugin_key(plugin_cls)
    if not plugin_allowed(key):
        return False
    if key in SYSTEM_PLUGINS:
        return True
    if group_id is None and user_id is not None:
        return plugin_settings_snapshot(group_id, user_id).get(key, False)
    gid = group_id if group_id is not None else 0
    try:
        conn = sqlite3.connect(str(_config.DB_PATH))
        cur = conn.execute(
            "SELECT 1 FROM group_plugin_config WHERE group_id = ? AND plugin_name = ?",
            (gid, key)
        )
        enabled = cur.fetchone() is not None
        conn.close()
        return enabled
    except sqlite3.Error:
        return True
