# 一些全局运行时数据
from datetime import datetime
from typing import TYPE_CHECKING
import sqlite3

if TYPE_CHECKING:
    from core.base import Plugin

script_start_time = datetime.now()
llonebot_data_path = "/app/llonebot/server_data"    # 使用api是用这个地址
python_data_path = "./server_data"                  # 在python脚本中访问用这个地址
onebot_qq_volume = "/var/lib/docker/volumes/onebot_qq_volume/_data"
startup_changelog_sent = True
plugin_registry: list[type["Plugin"]] = []
DEFAULT_GROUP_ID = 296470819 # 在这里填写你想固定使用的群号

# 系统级插件（不可按群禁用，始终运行）
SYSTEM_PLUGINS = frozenset({
    "menu",
    "group_manager",
    "startup_changelog",
    "backup",
    "update",
    "auto_friend",
    "welcome",
})

def plugin_key(plugin_cls: type["Plugin"]) -> str:
    return plugin_cls.__module__.split(".", 1)[1]

def is_plugin_enabled(plugin_cls: type["Plugin"], group_id: int | None) -> bool:
    key = plugin_key(plugin_cls)
    if key in SYSTEM_PLUGINS:
        return True
    gid = group_id if group_id is not None else 0
    try:
        conn = sqlite3.connect("data.db")
        cur = conn.execute(
            "SELECT 1 FROM group_plugin_config WHERE group_id = ? AND plugin_name = ?",
            (gid, key)
        )
        enabled = cur.fetchone() is not None
        conn.close()
        return enabled
    except sqlite3.Error:
        return True

def migrate_group_plugin_config():
    conn = sqlite3.connect("data.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS group_plugin_config (
            group_id INTEGER NOT NULL,
            plugin_name TEXT NOT NULL,
            PRIMARY KEY (group_id, plugin_name)
        )
    """)
    cur = conn.execute("SELECT COUNT(*) FROM group_plugin_config")
    if cur.fetchone()[0] > 0:
        conn.close()
        return
    rows = [(DEFAULT_GROUP_ID, plugin_key(cls)) for cls in plugin_registry
            if plugin_key(cls) not in SYSTEM_PLUGINS]
    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO group_plugin_config (group_id, plugin_name) VALUES (?, ?)", rows
        )
    conn.commit()
    conn.close()
