"""账号覆盖不改变群设置，缺行沿用私聊公共默认。"""
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.db._base import init_schema
from core.db.plugin_settings import enabled_plugins, set_user_plugins


@pytest.fixture
def conn():
    db = sqlite3.connect(":memory:")
    init_schema(db, db.cursor())
    yield db
    db.close()


def test_private_three_states_and_group_isolation(conn):
    conn.execute("INSERT INTO group_plugin_config VALUES (0, 'title')")
    conn.execute("INSERT INTO group_plugin_config VALUES (10, 'weekly_quest')")
    conn.commit()
    assert enabled_plugins(conn, user_id=1) == {"title": True}
    set_user_plugins(conn, 1, ["title"], False)
    set_user_plugins(conn, 1, ["weekly_quest"], True)
    assert enabled_plugins(conn, user_id=1) == {"title": False, "weekly_quest": True}
    assert enabled_plugins(conn, user_id=2) == {"title": True}
    assert enabled_plugins(conn, group_id=10, user_id=1) == {"weekly_quest": True}
    set_user_plugins(conn, 1, ["title", "weekly_quest"], None)
    assert enabled_plugins(conn, user_id=1) == {"title": True}


def test_snapshot_survives_later_changes(conn):
    set_user_plugins(conn, 1, ["title"], True)
    snapshot = enabled_plugins(conn, user_id=1)
    set_user_plugins(conn, 1, ["title"], False)
    assert snapshot["title"] is True
    assert enabled_plugins(conn, user_id=1)["title"] is False


def test_management_requires_superuser_and_uses_explicit_account(conn, tmp_path, monkeypatch):
    from core import config, context
    from core.base import SUPER_USER
    from plugins.group_manager import GroupManagerPlugin

    path = tmp_path / "controls.db"
    disk = sqlite3.connect(path)
    conn.backup(disk)
    disk.close()
    monkeypatch.setattr(config, "DB_PATH", path)
    title_cls = type("Title", (), {"__module__": "plugins.title"})
    monkeypatch.setattr(context, "plugin_registry", [title_cls])
    plugin = GroupManagerPlugin.__new__(GroupManagerPlugin)
    plugin.api = Mock()
    plugin.cmd = "/插件"
    plugin.args = ["title", "关闭", "用户", "42"]
    plugin.bot_event = SimpleNamespace(user_id=-1, group_id=None)
    plugin.handle()
    disk = sqlite3.connect(path)
    try:
        assert disk.execute("SELECT COUNT(*) FROM user_plugin_config").fetchone()[0] == 0
        plugin.bot_event.user_id = SUPER_USER[0]
        plugin.handle()
        assert enabled_plugins(disk, user_id=42) == {"title": False}
        plugin.args = ["title", "默认", "用户", "42"]
        plugin.handle()
        assert enabled_plugins(disk, user_id=42) == {}
        plugin.args = ["title", "开启", "群", "42"]
        plugin.handle()
        assert enabled_plugins(disk, group_id=42) == {"title": True}
        assert enabled_plugins(disk, user_id=42) == {}
        plugin.args = ["title", "off", "42"]  # 旧指令仍以末尾数字为群号
        plugin.handle()
        assert enabled_plugins(disk, group_id=42) == {}
    finally:
        disk.close()


def test_schema_upgrade_is_repeatable_and_preserves_rows(conn):
    conn.execute("INSERT INTO group_plugin_config VALUES (0, 'title')")
    conn.commit()
    set_user_plugins(conn, 1, ["title"], False)
    init_schema(conn, conn.cursor())
    assert enabled_plugins(conn, user_id=1) == {"title": False}
    assert enabled_plugins(conn, user_id=2) == {"title": True}
