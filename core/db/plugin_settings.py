"""群与私聊账号插件设置；读快照使用一条 SQL，账号关闭必须保存为 0。"""


def enabled_plugins(conn, group_id=None, user_id=None):
    rows = conn.execute("""
        SELECT plugin_name, 1, 0 FROM group_plugin_config WHERE group_id = ?
        UNION ALL
        SELECT plugin_name, enabled, 1 FROM user_plugin_config
        WHERE ? IS NULL AND user_id = ?
        ORDER BY 3
    """, (0 if group_id is None else group_id, group_id, str(user_id))).fetchall()
    return {name: bool(enabled) for name, enabled, _ in rows}


def set_user_plugins(conn, user_id, names, enabled):
    """enabled=None 恢复默认；调用方必须完成权限和插件合法性检查。"""
    with conn:
        for name in names:
            if enabled is None:
                conn.execute("DELETE FROM user_plugin_config WHERE user_id = ? AND plugin_name = ?",
                             (str(user_id), name))
            else:
                conn.execute("""
                    INSERT INTO user_plugin_config (user_id, plugin_name, enabled) VALUES (?, ?, ?)
                    ON CONFLICT(user_id, plugin_name) DO UPDATE SET enabled = excluded.enabled
                """, (str(user_id), name, int(bool(enabled))))
