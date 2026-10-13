"""查询不修改开关；注册账号、群与公共默认分别验证。"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core import config, context
from core.base import SUPER_USER
from core.database_manager import DbManager
from core.db.plugin_settings import set_user_plugins
from plugins import group_manager
from plugins.register import RegisterPlugin
from plugins.menu.entries import render_menu


@pytest.fixture
def query(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DB_PATH', tmp_path / 'query.db')
    monkeypatch.setattr(config, 'REGISTER_REQUIRE', False)
    monkeypatch.setattr(config, 'GROUP_REVIEW_REQUIRE', False)
    monkeypatch.setattr(context, 'ALLOWED_PLUGINS', None)
    monkeypatch.setattr(context, 'SYSTEM_PLUGINS', frozenset({'menu', 'register'}))
    monkeypatch.setattr(context, 'plugin_registry', [
        type(name, (), {'__module__': 'plugins.' + name})
        for name in ('menu', 'register', 'checkin', 'title', 'checkin')])
    monkeypatch.setattr(group_manager, 'FEATURE_PACKS', {
        '测试包': {'plugins': ['checkin', 'title', 'checkin', 'menu']}})
    db = DbManager()
    def run(args=('列表',), cmd='/插件', uid=SUPER_USER[0], gid=None):
        p = group_manager.GroupManagerPlugin.__new__(group_manager.GroupManagerPlugin)
        p.bot_event = SimpleNamespace(user_id=uid, group_id=gid)
        p.api, p.cmd, p.args = Mock(), cmd, list(args)
        p.handle()
        return p.api.send_msg.call_args.args[0]['data']['text']
    yield SimpleNamespace(db=db, run=run)
    db.conn.close()


def test_target_registration_uses_current_account(query, monkeypatch):
    monkeypatch.setattr(config, 'REGISTER_DEFAULT_PACK', '基础包')
    p = RegisterPlugin.__new__(RegisterPlugin)
    p.dbmanager = query.db
    query.db.community.register_user(SUPER_USER[0])
    p._seed_default_pack(SUPER_USER[0])
    assert '/打卡' in render_menu(context.plugin_settings_snapshot(None, SUPER_USER[0]), False, False)
    assert '✅ checkin' in query.run()
    assert str(SUPER_USER[0]) in query.run()
    assert '✅ checkin' in query.run(['列表', '用户', str(SUPER_USER[0])])
    assert '测试包 (1/2)' in query.run(cmd='/功能包')


def test_target_group_and_numeric_scope(query):
    set_user_plugins(query.db.conn, SUPER_USER[0], ['checkin'], True)
    query.db.conn.execute("INSERT INTO group_plugin_config VALUES (100, 'title')")
    query.db.conn.commit()
    for args, gid in [(['列表'], 100), (['列表', '群', '100'], None), (['列表', '100'], None)]:
        out = query.run(args, gid=gid)
        assert '群100' in out and '✅ title' in out and '❌ checkin' in out


def test_defaults_alias_excludes_account_settings(query):
    set_user_plugins(query.db.conn, SUPER_USER[0], ['checkin'], True)
    for cmd in ('/插件', '/功能包'):
        a = query.run(['列表', '公共默认'], cmd=cmd)
        assert a == query.run(['列表', '0'], cmd=cmd)
        assert '私聊公共默认' in a and '继承' in a
        assert '✅ checkin' not in a
        if cmd == '/功能包':
            assert '默认开启' in a and '(0/2)' in a


def test_effective_target_registration_and_superuser_exemption(query, monkeypatch):
    monkeypatch.setattr(config, 'REGISTER_REQUIRE', True)
    set_user_plugins(query.db.conn, 42, ['checkin'], True)
    set_user_plugins(query.db.conn, SUPER_USER[0], ['checkin'], True)
    out = query.run(['列表', '用户', '42'])
    assert '未注册' in out and '✅ checkin' not in out and '已保存开启' in out
    assert '✅ checkin' in query.run()
    query.db.community.register_user(42)
    assert '✅ checkin' in query.run(['列表', '用户', '42'])


def test_effective_deployment_and_group_approval(query, monkeypatch):
    query.db.conn.execute("INSERT INTO group_plugin_config VALUES (100, 'checkin')")
    query.db.conn.commit()
    monkeypatch.setattr(config, 'GROUP_REVIEW_REQUIRE', True)
    out = query.run(['列表', '群', '100'])
    assert '群未批准' in out and '✅ checkin' not in out
    query.db.community.activate_group(100)
    assert '✅ checkin' in query.run(['列表', '群', '100'])
    monkeypatch.setattr(context, 'ALLOWED_PLUGINS', frozenset({'menu', 'register', 'title'}))
    out = query.run(['列表', '群', '100'])
    assert '部署未开放' in out and '✅ checkin' not in out


def test_effective_read_failure_is_unknown(query):
    query.db.conn.execute('DROP TABLE user_plugin_config')
    query.db.conn.commit()
    assert '无法确认' in query.run()


def test_pack_deployment_count_and_unique_keys(query, monkeypatch):
    set_user_plugins(query.db.conn, SUPER_USER[0], ['checkin', 'title'], True)
    assert query.run().count('✅ checkin') == 1
    monkeypatch.setattr(context, 'ALLOWED_PLUGINS', frozenset({'menu', 'register', 'checkin'}))
    out = query.run(cmd='/功能包')
    assert '(1/1)' in out and '部署未开放1项' in out
    monkeypatch.setattr(context, 'ALLOWED_PLUGINS', frozenset({'menu', 'register'}))
    out = query.run(cmd='/功能包')
    assert '无可计数' in out and '✅' not in out


def test_pack_account_closed_and_inherited(query):
    query.db.conn.execute("INSERT INTO group_plugin_config VALUES (0, 'checkin')")
    query.db.conn.commit()
    assert 'checkin（沿用默认）' in query.run()
    set_user_plugins(query.db.conn, SUPER_USER[0], ['checkin'], False)
    assert '❌ checkin（单独设置）' in query.run()
    assert '(0/2)' in query.run(cmd='/功能包')


def test_compatibility_no_writes_and_write_scope_unchanged(query):
    before = '\n'.join(query.db.conn.iterdump())
    query.run(); query.run(cmd='/功能包'); query.run(['列表', '公共默认'])
    assert before == '\n'.join(query.db.conn.iterdump())
    assert '仅超级用户' in query.run(uid=42)
    assert '仅超级用户' in query.run(['checkin', '开启'], uid=42)
    reply = query.run(['checkin', '开启'])
    assert '私聊公共默认' in reply and '继承' in reply
    assert query.db.conn.execute('SELECT group_id FROM group_plugin_config').fetchone()[0] == 0
    assert not query.db.conn.execute('SELECT * FROM user_plugin_config').fetchall()
    assert '用户 <账号>' in query.run()


def test_effective_registration_exceptions_match_runtime(query, monkeypatch):
    monkeypatch.setattr(config, 'REGISTER_REQUIRE', True)
    out = query.run(['列表', '用户', '42'])
    assert '🔒 register（系统插件）' in out
    assert '🚫 menu（账号未注册；系统插件）' in out  # 使用实际运行期标识，不另造菜单豁免
    assert context.register_gate('message', None, 42) == context.REGISTRATION_ALLOWLIST


def test_pack_restricted_targets_and_system_only(query, monkeypatch):
    set_user_plugins(query.db.conn, 42, ['checkin', 'title'], True)
    monkeypatch.setattr(config, 'REGISTER_REQUIRE', True)
    out = query.run(['列表', '用户', '42'], cmd='/功能包')
    assert '(0/2)' in out and '账号未注册' in out
    monkeypatch.setattr(group_manager, 'FEATURE_PACKS', {'系统包': {'plugins': ['menu']}})
    out = query.run(cmd='/功能包')
    assert '仅系统插件' in out and '✅' not in out


def test_compatibility_explicit_actions_restore_and_group(query):
    for cmd, name in [('/插件', 'checkin'), ('/功能包', '测试包')]:
        query.run([name, '开启', '用户', '42'], cmd=cmd)
        assert query.db.conn.execute('SELECT * FROM user_plugin_config WHERE user_id=42').fetchall()
        query.run([name, '默认', '用户', '42'], cmd=cmd)
        assert not query.db.conn.execute('SELECT * FROM user_plugin_config WHERE user_id=42').fetchall()
        query.run([name, '开启'], cmd=cmd, gid=100)
        assert query.db.conn.execute('SELECT * FROM group_plugin_config WHERE group_id=100').fetchall()
    assert '群100' in query.run(['列表', 'off', '100'])
    assert '私聊公共默认' in query.run(['列表', 'off', '0'])


def test_compatibility_help_and_community_menu(query, monkeypatch):
    from pathlib import Path
    import yaml
    from core import text_pack
    path = Path(__file__).resolve().parents[1] / 'text_packs/community.yaml'
    monkeypatch.setattr(text_pack, '_pack', yaml.safe_load(path.read_text(encoding='utf-8')))
    menu = render_menu({'group_manager': True}, True, False)
    assert '/插件 列表 公共默认' in menu and '/功能包 列表 公共默认' in menu
    assert '私聊查本人' in menu and '私聊修改私聊公共设置' in menu
    help_text = query.run([])
    assert '列表 公共默认' in help_text and '影响继承账号' in help_text


@pytest.mark.parametrize('args', [['列表', '用户', '-1'], ['列表', '公共默认', '42'], ['列表', '群', '0']])
def test_compatibility_invalid_target(query, args):
    before = '\n'.join(query.db.conn.iterdump())
    assert '用法' in query.run(args)
    assert before == '\n'.join(query.db.conn.iterdump())
