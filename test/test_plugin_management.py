"""第3部分：超级用户权限、显式目标、账号三态、功能包批量和错误输入。"""
import sqlite3
from pathlib import Path

import yaml
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core import config, context
from core.base import SUPER_USER
from core.db._base import init_schema
from core.db.plugin_settings import enabled_plugins, set_user_plugins
from plugins import group_manager


@pytest.fixture
def management(tmp_path, monkeypatch):
    path = tmp_path / "management.db"
    conn = sqlite3.connect(path)
    init_schema(conn, conn.cursor())
    monkeypatch.setattr(config, "DB_PATH", path)
    monkeypatch.setattr(context, "SYSTEM_PLUGINS", frozenset({"menu"}))
    monkeypatch.setattr(context, "plugin_registry", [
        type(name, (), {"__module__": f"plugins.{name}"}) for name in ("title", "weekly_quest", "menu")
    ])
    monkeypatch.setattr(group_manager, "FEATURE_PACKS", {
        "测试包": {"plugins": ["title", "weekly_quest", "menu"]},
    })

    def run(cmd, args, uid=SUPER_USER[0], gid=None):
        plugin = group_manager.GroupManagerPlugin.__new__(group_manager.GroupManagerPlugin)
        plugin.cmd, plugin.args = cmd, args
        plugin.api = Mock()
        plugin.bot_event = SimpleNamespace(user_id=uid, group_id=gid, sender={"role": "owner"})
        plugin.handle()
        return plugin.api.send_msg.call_args.args[0]["data"]["text"]

    yield SimpleNamespace(conn=conn, run=run)
    conn.close()


@pytest.mark.parametrize("cmd,name", [("/插件", "title"), ("/功能包", "测试包")])
@pytest.mark.parametrize("scope", ["群", "用户"])
def test_only_superuser_may_change_any_target(management, cmd, name, scope):
    assert management.run(cmd, [name, "开启", scope, "42"], uid=-1) == "仅超级用户可管理插件"
    assert management.conn.execute("SELECT COUNT(*) FROM user_plugin_config").fetchone()[0] == 0
    assert management.conn.execute("SELECT COUNT(*) FROM group_plugin_config").fetchone()[0] == 0


def test_user_pack_three_states_and_list(management):
    db, run = management.conn, management.run
    db.execute("INSERT INTO group_plugin_config VALUES (0, 'title')")
    db.commit()
    run("/功能包", ["测试包", "开启", "用户", "42"])
    assert enabled_plugins(db, user_id=42) == {"title": True, "weekly_quest": True}
    assert enabled_plugins(db, user_id=43) == {"title": True}
    assert "测试包 (2/2)" in run("/功能包", ["列表", "用户", "42"])
    assert "title（单独设置）" in run("/插件", ["列表", "用户", "42"])
    run("/功能包", ["测试包", "关闭", "用户", "42"])
    assert enabled_plugins(db, user_id=42) == {"title": False, "weekly_quest": False}
    assert "测试包 (0/2)" in run("/功能包", ["列表", "用户", "42"])
    run("/功能包", ["测试包", "默认", "用户", "42"])
    assert enabled_plugins(db, user_id=42) == {"title": True}
    assert "title（沿用默认）" in run("/插件", ["列表", "用户", "42"])
    assert db.execute("SELECT COUNT(*) FROM user_plugin_config WHERE plugin_name='menu'").fetchone()[0] == 0


def test_system_plugin_remains_enabled_even_with_stale_override(management):
    set_user_plugins(management.conn, 42, ["menu"], False)
    assert context.plugin_settings_snapshot(None, 42)["menu"] is True


def test_menu_and_community_pack_explain_account_commands():
    from plugins.menu.bot_menu_text import BOT_MENU_TEXT
    root = Path(__file__).resolve().parents[1]
    community = yaml.safe_load((root / "text_packs/community.yaml").read_text(encoding="utf-8"))["menu_text"]
    for menu in (BOT_MENU_TEXT, community):
        for expected in (
            "/插件 <name> <开启|关闭|默认> 用户 <账号>",
            "/功能包 <name> <开启|关闭|默认> 用户 <账号>",
            "/插件 列表 用户 <账号>", "/功能包 列表 用户 <账号>",
            "私聊修改私聊公共设置", "系统插件不能关闭",
        ):
            assert expected in menu


def test_help_explains_restore_default(management):
    for command in ("/插件", "/功能包"):
        help_text = management.run(command, [])
        assert "账号设置" in help_text and "默认表示沿用私聊公共设置" in help_text


def test_legacy_scopes_and_explicit_group_pack(management):
    db, run = management.conn, management.run
    run("/插件", ["title"])
    assert enabled_plugins(db, user_id=42) == {"title": True}
    run("/插件", ["title", "off"])
    assert enabled_plugins(db, user_id=42) == {}
    run("/插件", ["title"], gid=10)
    assert enabled_plugins(db, group_id=10) == {"title": True}
    run("/插件", ["title", "off", "10"], gid=11)
    assert enabled_plugins(db, group_id=10) == {}
    run("/功能包", ["测试包", "开启", "群", "11"])
    assert enabled_plugins(db, group_id=11) == {"title": True, "weekly_quest": True}
    run("/功能包", ["测试包", "关闭", "群", "11"])
    assert enabled_plugins(db, group_id=11) == {}


@pytest.mark.parametrize("args", [
    ["menu", "关闭", "用户", "42"], ["menu", "关闭", "群", "42"],
    ["title", "默认", "群", "42"], ["title", "开启", "用户", "0"],
    ["title", "开启", "用户", "-1"], ["title", "开启", "用户", "abc"],
    ["title", "开启", "用户", "999999999999999999999999"],
    ["title", "开启", "用户", "４２"], ["title", "用户", "42"],
    ["title", "随便", "用户", "42"], ["不存在", "开启", "用户", "42"],
    ["title", "默认"], ["title", "off", "not-a-group"],
])
def test_invalid_or_system_changes_do_not_write(management, args):
    assert management.run("/插件", args)
    assert management.conn.execute("SELECT COUNT(*) FROM user_plugin_config").fetchone()[0] == 0
    assert management.conn.execute("SELECT COUNT(*) FROM group_plugin_config").fetchone()[0] == 0


@pytest.mark.parametrize("identity,code", [(None, 401), (-1, 403)])
def test_monitoring_panel_rejects_non_superuser_before_reading_update(identity, code, monkeypatch):
    from core import web_panel
    handler = web_panel.PanelHandler.__new__(web_panel.PanelHandler)
    handler.path = "/api/plugins"
    handler.headers = {"Authorization": "Bearer test-only-token"}
    handler._json = Mock()
    handler._body = Mock(side_effect=AssertionError("未授权请求不应读取修改参数"))
    monkeypatch.setattr(web_panel, "verify_login_key", lambda token: identity)
    handler.do_PUT()
    assert handler._json.call_args.args[0] == code
    handler._body.assert_not_called()


def test_user_batch_failure_rolls_back_every_change(management):
    db = management.conn
    db.execute("""CREATE TRIGGER reject_test_user BEFORE INSERT ON user_plugin_config
                  WHEN NEW.plugin_name='weekly_quest'
                  BEGIN SELECT RAISE(ABORT, 'test failure'); END""")
    db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        set_user_plugins(db, 42, ["title", "weekly_quest"], True)
    assert enabled_plugins(db, user_id=42) == {}


def test_group_batch_failure_rolls_back_every_change(management):
    db = management.conn
    db.execute("""CREATE TRIGGER reject_test_group BEFORE INSERT ON group_plugin_config
                  WHEN NEW.plugin_name='weekly_quest'
                  BEGIN SELECT RAISE(ABORT, 'test failure'); END""")
    db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        group_manager._set_pack_config(10, "测试包", True)
    assert enabled_plugins(db, group_id=10) == {}
